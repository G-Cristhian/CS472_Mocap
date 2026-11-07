"""
Multi-Model Pose Detector Wrapper for Live Streaming.
Supports:
  1. MediaPipe PoseLandmarker (Lite, Full, Heavy) running in VIDEO mode.
  2. RTMPose (Tau-J / MMPose Halpe-26) running on ONNX Runtime with
     hardware acceleration (DirectML / CUDA / CPU).
"""
from __future__ import annotations

import logging
from pathlib import Path
import sys
import threading
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

logger = logging.getLogger("live_detector")

# Process-wide lock for GPU execution providers (DirectML / CUDA)
# DirectML command queues are not thread-safe for concurrent operator dispatches
ORT_GPU_LOCK = threading.RLock()
_SHARED_RTMLIB_MODELS: Dict[Tuple[str, str], Any] = {}

# Landmark names in MediaPipe order (0 to 32)
LANDMARK_NAMES = [
    "NOSE", "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER",
    "RIGHT_EYE_INNER", "RIGHT_EYE", "RIGHT_EYE_OUTER",
    "LEFT_EAR", "RIGHT_EAR", "MOUTH_LEFT", "MOUTH_RIGHT",
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_PINKY", "RIGHT_PINKY",
    "LEFT_INDEX", "RIGHT_INDEX", "LEFT_THUMB", "RIGHT_THUMB",
    "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE",
    "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL", "RIGHT_HEEL",
    "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX",
]

# Standard MediaPipe connections
POSE_CONNECTIONS = [
    # Face
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    # Torso
    (11, 12), (11, 23), (12, 24), (23, 24),
    # Left arm
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    # Right arm
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    # Left leg
    (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
    # Right leg
    (24, 26), (26, 28), (28, 30), (28, 32), (30, 32),
]

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def resolve_model_path(model_variant: str = "full") -> Path:
    """Finds model file for lite, full, or heavy MediaPipe variant."""
    candidates = [
        MODELS_DIR / f"pose_landmarker_{model_variant}.task",
        MODELS_DIR / "pose_landmarker_full.task",
        MODELS_DIR / "pose_landmarker_heavy.task",
        MODELS_DIR / "pose_landmarker_lite.task",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"No MediaPipe pose_landmarker model found in {MODELS_DIR}")


def get_best_onnx_device() -> str:
    """
    Detects best available execution provider for ONNX Runtime:
    Returns 'dml' (DirectML on Windows GPU), 'cuda' (NVIDIA CUDA), or 'cpu'.
    """
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if "DmlExecutionProvider" in providers:
            return "dml"
        if "CUDAExecutionProvider" in providers:
            return "cuda"
    except Exception:
        pass
    return "cpu"


class LivePoseDetector:
    """
    MediaPipe PoseLandmarker running in VIDEO mode for smooth temporal tracking.
    """
    def __init__(self, model_variant: str = "full", min_detection_confidence: float = 0.5):
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self.model_name = "mediapipe"
        self.model_variant = model_variant
        self.model_path = resolve_model_path(model_variant)
        self.min_confidence = min_detection_confidence

        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_detection_confidence,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._last_ms = -1

    def close(self):
        try:
            self._landmarker.close()
        except Exception:
            pass

    def detect(self, rgb_frame: np.ndarray, frame_ms: float) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
        """
        Runs detection on an RGB frame.
        """
        import mediapipe as mp

        height, width = rgb_frame.shape[:2]
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Ensure monotonically increasing timestamp
        timestamp_ms = max(int(round(frame_ms)), self._last_ms + 1)
        self._last_ms = timestamp_ms

        try:
            result = self._landmarker.detect_for_video(image, timestamp_ms)
        except Exception as e:
            logger.warning(f"MediaPipe detect error: {e}")
            return None, None

        if not result.pose_landmarks or len(result.pose_landmarks) == 0:
            return None, None

        landmarks_2d = []
        for i, lm in enumerate(result.pose_landmarks[0]):
            name = LANDMARK_NAMES[i] if i < len(LANDMARK_NAMES) else f"JOINT_{i}"
            landmarks_2d.append({
                "index": i,
                "name": name,
                "x": float(lm.x),
                "y": float(lm.y),
                "z": float(lm.z) if lm.z is not None else 0.0,
                "visibility": float(lm.visibility) if lm.visibility is not None else 1.0,
                "px_x": float(lm.x * width),
                "px_y": float(lm.y * height),
            })

        world_landmarks_3d = []
        if result.pose_world_landmarks and len(result.pose_world_landmarks) > 0:
            for i, lm in enumerate(result.pose_world_landmarks[0]):
                name = LANDMARK_NAMES[i] if i < len(LANDMARK_NAMES) else f"JOINT_{i}"
                world_landmarks_3d.append({
                    "index": i,
                    "name": name,
                    "x": float(lm.x),
                    "y": float(-lm.y),  # Inverted Y for standard 3D coordinate space (Y-up)
                    "z": float(-lm.z) if lm.z is not None else 0.0,
                    "visibility": float(lm.visibility) if lm.visibility is not None else 1.0,
                })
        else:
            world_landmarks_3d = None

        return landmarks_2d, world_landmarks_3d


class LiveRTMPoseDetector:
    """
    RTMPose with Halpe-26 keypoints (body with feet) powered by ONNX Runtime.
    Hardware-accelerated via DirectML (DirectX 12 on Windows) or CUDA.
    """
    def __init__(self, mode: str = "balanced", device: str = "auto"):
        # Register DirectML provider in rtmlib if present
        try:
            from rtmlib.tools.base import RTMLIB_SETTINGS
            if "dml" not in RTMLIB_SETTINGS.get("onnxruntime", {}):
                RTMLIB_SETTINGS["onnxruntime"]["dml"] = "DmlExecutionProvider"
        except Exception:
            pass

        self.model_name = "rtmpose"
        self.mode = mode  # "lightweight", "balanced", or "performance"
        target_device = get_best_onnx_device() if device == "auto" else device
        self.device = target_device

        logger.info(f"Initializing RTMPose on device '{self.device}' (mode: {self.mode})...")

        from rtmlib import BodyWithFeet
        cache_key = (self.mode, self.device)
        with ORT_GPU_LOCK:
            if cache_key not in _SHARED_RTMLIB_MODELS:
                logger.info(f"Loading shared BodyWithFeet model for {cache_key}...")
                _SHARED_RTMLIB_MODELS[cache_key] = BodyWithFeet(
                    mode=self.mode,
                    backend="onnxruntime",
                    device=self.device,
                )
            self._model = _SHARED_RTMLIB_MODELS[cache_key]

        # Import backend helpers
        backend_dir = Path(__file__).resolve().parent.parent
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))

        from mocap_pipeline.stage1_keypoints.backends import (
            pick_person,
            halpe26_to_mediapipe,
            HALPE26_JOINTS,
            MEDIAPIPE_FROM_HALPE26,
        )
        from mocap_pipeline.joints import JOINT_INDEX

        self._pick_person = pick_person
        self._halpe26_to_mediapipe = halpe26_to_mediapipe

    def close(self):
        # Retain model instance in shared cache so other cameras or switches can reuse it
        self._model = None

    def detect(self, rgb_frame: np.ndarray, frame_ms: float) -> Tuple[Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
        """
        Runs detection on an RGB frame.
        Returns:
            landmarks_2d: 33 items in MediaPipe order
            world_landmarks_3d: 33 items (reconstructed metric 3D points)
        """
        if self._model is None:
            return None, None

        height, width = rgb_frame.shape[:2]
        bgr = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

        with ORT_GPU_LOCK:
            try:
                bboxes = np.asarray(self._model.det_model(bgr)).reshape(-1, 4)
                person_idx = self._pick_person(bboxes)
                if person_idx is None:
                    return None, None

                keypoints, scores = self._model.pose_model(bgr, bboxes=[bboxes[person_idx]])
                if keypoints is None or len(keypoints) == 0:
                    return None, None
            except Exception as e:
                logger.warning(f"RTMPose inference error: {e}")
                return None, None

        # Convert Halpe-26 to MediaPipe (33, 2) and confidence (33,)
        pts, conf = self._halpe26_to_mediapipe(keypoints[0], scores[0])

        landmarks_2d = []
        for i in range(33):
            name = LANDMARK_NAMES[i]
            x_px, y_px = pts[i, 0], pts[i, 1]
            vis = float(conf[i])
            if np.isnan(x_px) or np.isnan(y_px) or vis <= 0.0:
                landmarks_2d.append({
                    "index": i,
                    "name": name,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "visibility": 0.0,
                    "px_x": 0.0,
                    "px_y": 0.0,
                })
            else:
                landmarks_2d.append({
                    "index": i,
                    "name": name,
                    "x": float(x_px / width),
                    "y": float(y_px / height),
                    "z": 0.0,
                    "visibility": vis,
                    "px_x": float(x_px),
                    "px_y": float(y_px),
                })

        # Monocular 3D estimation for single-camera preview
        # Center around hips
        world_landmarks_3d = self._estimate_monocular_world_3d(landmarks_2d, width, height)

        return landmarks_2d, world_landmarks_3d

    def _estimate_monocular_world_3d(
        self,
        landmarks_2d: List[Dict[str, Any]],
        width: int,
        height: int,
    ) -> List[Dict[str, Any]]:
        """
        Constructs normalized metric 3D skeleton from RTMPose 2D keypoints
        using biomechanical kinematic constraints for realistic 3D depth.
        """
        by_name = {lm["name"]: lm for lm in landmarks_2d}

        # Find hip center
        l_hip = by_name.get("LEFT_HIP")
        r_hip = by_name.get("RIGHT_HIP")
        if l_hip and r_hip and l_hip["visibility"] > 0.2 and r_hip["visibility"] > 0.2:
            hip_cx = (l_hip["px_x"] + r_hip["px_x"]) * 0.5
            hip_cy = (l_hip["px_y"] + r_hip["px_y"]) * 0.5
        else:
            hip_cx, hip_cy = width * 0.5, height * 0.5

        # Normalization scale (performer height on screen)
        l_ankle = by_name.get("LEFT_ANKLE")
        r_ankle = by_name.get("RIGHT_ANKLE")
        l_sh = by_name.get("LEFT_SHOULDER")
        r_sh = by_name.get("RIGHT_SHOULDER")
        nose = by_name.get("NOSE")

        scale = 1.0 / max(height * 0.5, 1.0)
        has_feet = (l_ankle and l_ankle["visibility"] > 0.2) or (r_ankle and r_ankle["visibility"] > 0.2)

        if nose and nose["visibility"] > 0.2 and has_feet:
            foot_y = max(
                (l_ankle["px_y"] if l_ankle and l_ankle["visibility"] > 0.2 else 0.0),
                (r_ankle["px_y"] if r_ankle and r_ankle["visibility"] > 0.2 else 0.0),
            )
            h_span = max(foot_y - nose["px_y"], 50.0)
            scale = 1.75 / h_span
        elif l_sh and r_sh and l_sh["visibility"] > 0.2 and r_sh["visibility"] > 0.2:
            sh_cy = (l_sh["px_y"] + r_sh["px_y"]) * 0.5
            torso_span = max(abs(hip_cy - sh_cy), 30.0)
            scale = 0.50 / torso_span  # 0.50m nominal torso length
        elif l_sh and r_sh:
            sh_w = max(abs(l_sh["px_x"] - r_sh["px_x"]), 20.0)
            scale = 0.38 / sh_w

        # Compute initial XY in meters relative to hip center
        xy_m: Dict[str, Tuple[float, float]] = {}
        for lm in landmarks_2d:
            rel_x = (lm["px_x"] - hip_cx) * scale
            rel_y = -(lm["px_y"] - hip_cy) * scale
            xy_m[lm["name"]] = (rel_x, rel_y)

        # Volumetric depth without artificial forward-only clamping or length caps
        z_m: Dict[str, float] = {k: 0.0 for k in xy_m}

        # Head offset
        for k in ("NOSE", "LEFT_EYE", "RIGHT_EYE", "MOUTH_LEFT", "MOUTH_RIGHT"):
            if k in z_m:
                z_m[k] = 0.05

        # Torso inclination depth
        if l_sh and r_sh and l_hip and r_hip:
            sh_z = 0.0
            hip_z = 0.0
            z_m["LEFT_SHOULDER"] = sh_z
            z_m["RIGHT_SHOULDER"] = sh_z
            z_m["LEFT_HIP"] = hip_z
            z_m["RIGHT_HIP"] = hip_z

        # Continuous limb depth without artificial locking
        def track_limb_z(parent_name: str, child_name: str, sign: float = 1.0):
            if parent_name not in xy_m or child_name not in xy_m:
                return
            px, py = xy_m[parent_name]
            cx, cy = xy_m[child_name]
            d = float(np.sqrt((cx - px) ** 2 + (cy - py) ** 2))
            # Smooth unconstrained depth variation
            z_m[child_name] = z_m[parent_name] + sign * (d * 0.25)

        track_limb_z("LEFT_SHOULDER", "LEFT_ELBOW", sign=0.5)
        track_limb_z("LEFT_ELBOW", "LEFT_WRIST", sign=0.5)
        track_limb_z("RIGHT_SHOULDER", "RIGHT_ELBOW", sign=0.5)
        track_limb_z("RIGHT_ELBOW", "RIGHT_WRIST", sign=0.5)

        track_limb_z("LEFT_HIP", "LEFT_KNEE", sign=0.3)
        track_limb_z("LEFT_KNEE", "LEFT_ANKLE", sign=-0.2)
        track_limb_z("RIGHT_HIP", "RIGHT_KNEE", sign=0.3)
        track_limb_z("RIGHT_KNEE", "RIGHT_ANKLE", sign=-0.2)

        for k in ("LEFT_HEEL", "LEFT_FOOT_INDEX"):
            if k in z_m and "LEFT_ANKLE" in z_m:
                z_m[k] = z_m["LEFT_ANKLE"] + (0.08 if "FOOT_INDEX" in k else -0.04)
        for k in ("RIGHT_HEEL", "RIGHT_FOOT_INDEX"):
            if k in z_m and "RIGHT_ANKLE" in z_m:
                z_m[k] = z_m["RIGHT_ANKLE"] + (0.08 if "FOOT_INDEX" in k else -0.04)

        world_3d = []
        for lm in landmarks_2d:
            name = lm["name"]
            if lm["visibility"] > 0.05 and name in xy_m:
                rx, ry = xy_m[name]
                rz = z_m.get(name, 0.0)
                world_3d.append({
                    "index": lm["index"],
                    "name": name,
                    "x": float(rx),
                    "y": float(ry),
                    "z": float(rz),
                    "visibility": lm["visibility"],
                })
            else:
                world_3d.append({
                    "index": lm["index"],
                    "name": name,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "visibility": 0.0,
                })

        return world_3d


def create_live_detector(
    model_type: str = "mediapipe",
    variant: str = "full",
    device: str = "auto",
) -> Any:
    """
    Factory function to instantiate either MediaPipe or RTMPose detector.
    """
    m_type = model_type.lower().strip()
    if m_type in ("rtmpose", "rtm"):
        return LiveRTMPoseDetector(mode=variant if variant in ("lightweight", "balanced", "performance") else "balanced", device=device)
    else:
        return LivePoseDetector(model_variant=variant if variant in ("lite", "full", "heavy") else "full")


def draw_skeleton(bgr_image: np.ndarray, landmarks_2d: List[Dict[str, Any]]) -> np.ndarray:
    """
    Draws 2D skeleton onto BGR image using OpenCV.
    """
    img = bgr_image.copy()
    h, w = img.shape[:2]

    pts = {}
    for lm in landmarks_2d:
        if lm["visibility"] >= 0.3:
            x = int(lm["px_x"]) if "px_x" in lm else int(lm["x"] * w)
            y = int(lm["px_y"]) if "px_y" in lm else int(lm["y"] * h)
            pts[lm["index"]] = (x, y)

    # Draw bones
    for start_idx, end_idx in POSE_CONNECTIONS:
        if start_idx in pts and end_idx in pts:
            color = (0, 255, 255)  # Cyan
            if start_idx in (11, 13, 15, 23, 25, 27):
                color = (255, 120, 50)  # Left limbs
            elif start_idx in (12, 14, 16, 24, 26, 28):
                color = (50, 160, 255)  # Right limbs

            cv2.line(img, pts[start_idx], pts[end_idx], color, 2, cv2.LINE_AA)

    # Draw joint circles
    for idx, (x, y) in pts.items():
        cv2.circle(img, (x, y), 4, (0, 255, 0), -1, cv2.LINE_AA)
        cv2.circle(img, (x, y), 5, (255, 255, 255), 1, cv2.LINE_AA)

    return img
