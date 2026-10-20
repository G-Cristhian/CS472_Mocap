"""
MediaPipe PoseLandmarker wrapper for real-time live streaming.
Extracts both 2D normalized landmarks and 3D metric world landmarks.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

# Landmark names in order (0 to 32)
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
    """
    Finds model file for lite, full, or heavy variant.
    Falls back to any available model in backend/models.
    """
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


class LivePoseDetector:
    """
    MediaPipe PoseLandmarker running in VIDEO mode for smooth temporal tracking.
    """
    def __init__(self, model_variant: str = "full", min_detection_confidence: float = 0.5):
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

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
        Returns:
            landmarks_2d: 33 items with {'x': 0..1, 'y': 0..1, 'z': relative, 'visibility': 0..1, 'name': str}
            world_landmarks_3d: 33 items with {'x': meters, 'y': meters, 'z': meters, 'visibility': 0..1, 'name': str}
        """
        import mediapipe as mp

        height, width = rgb_frame.shape[:2]
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Ensure monotonically increasing timestamp
        timestamp_ms = max(int(round(frame_ms)), self._last_ms + 1)
        self._last_ms = timestamp_ms

        result = self._landmarker.detect_for_video(image, timestamp_ms)

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
                # Invert Y so Y is UP for 3D viewers (MediaPipe world coords are Y-down)
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

    @staticmethod
    def draw_skeleton(bgr_image: np.ndarray, landmarks_2d: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draws 2D skeleton onto BGR image using OpenCV.
        """
        img = bgr_image.copy()
        h, w = img.shape[:2]

        pts = {}
        for lm in landmarks_2d:
            if lm["visibility"] >= 0.3:
                x = int(lm["x"] * w)
                y = int(lm["y"] * h)
                pts[lm["index"]] = (x, y)

        # Draw bones
        for start_idx, end_idx in POSE_CONNECTIONS:
            if start_idx in pts and end_idx in pts:
                # Limb coloring
                color = (0, 255, 255)  # Cyan default
                if start_idx in (11, 13, 15, 23, 25, 27):
                    color = (255, 120, 50)  # Left limbs: blue/purple in BGR
                elif start_idx in (12, 14, 16, 24, 26, 28):
                    color = (50, 160, 255)  # Right limbs: orange in BGR

                cv2.line(img, pts[start_idx], pts[end_idx], color, 2, cv2.LINE_AA)

        # Draw joint circles
        for idx, (x, y) in pts.items():
            cv2.circle(img, (x, y), 4, (0, 255, 0), -1, cv2.LINE_AA)
            cv2.circle(img, (x, y), 5, (255, 255, 255), 1, cv2.LINE_AA)

        return img
