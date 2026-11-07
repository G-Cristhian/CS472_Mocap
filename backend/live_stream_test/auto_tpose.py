"""
Automated T-Pose Detection and Auto-Calibration for Live Stream Mocap.

Monitors live 3D joint positions (or 2D keypoints), detects when the performer
assumes and stably holds a T-pose, and automatically calculates:
  1. Rigid segment bone lengths (shoulders, arms, torso, thighs, shins)
  2. Ground floor plane height (Y_floor = 0)
  3. Metric scaling factor based on configured performer height
  4. Neutral zero-rotation reference pose
"""
from __future__ import annotations

from collections import deque
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

logger = logging.getLogger("auto_tpose")

# Bones measured during T-pose calibration
BONE_DEFINITIONS: Dict[str, Tuple[str, str]] = {
    "upper_arm_left": ("LEFT_SHOULDER", "LEFT_ELBOW"),
    "forearm_left": ("LEFT_ELBOW", "LEFT_WRIST"),
    "upper_arm_right": ("RIGHT_SHOULDER", "RIGHT_ELBOW"),
    "forearm_right": ("RIGHT_ELBOW", "RIGHT_WRIST"),
    "shoulder_width": ("LEFT_SHOULDER", "RIGHT_SHOULDER"),
    "torso": ("HIP_MID", "SHOULDER_MID"),
    "thigh_left": ("LEFT_HIP", "LEFT_KNEE"),
    "shin_left": ("LEFT_KNEE", "LEFT_ANKLE"),
    "thigh_right": ("RIGHT_HIP", "RIGHT_KNEE"),
    "shin_right": ("RIGHT_KNEE", "RIGHT_ANKLE"),
    "hip_width": ("LEFT_HIP", "RIGHT_HIP"),
}


def _angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """
    Computes angle ABC at vertex B in degrees (0 to 180).
    Points must be (3,) arrays.
    """
    ba = a - b
    bc = c - b
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return 0.0
    cosine = np.clip(np.dot(ba, bc) / (norm_ba * norm_bc), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def normalize_joints_dict(joints_data: Any) -> Dict[str, np.ndarray]:
    """
    Converts either a list of landmark dicts or a joint dictionary into
    a clean Dict[str, np.ndarray] of 3D points.
    """
    res: Dict[str, np.ndarray] = {}
    if isinstance(joints_data, dict):
        for k, v in joints_data.items():
            if isinstance(v, (list, tuple, np.ndarray)) and len(v) >= 3:
                res[k.upper()] = np.asarray(v[:3], dtype=np.float64)
            elif isinstance(v, dict) and "x" in v and "y" in v:
                res[k.upper()] = np.array([v.get("x", 0.0), v.get("y", 0.0), v.get("z", 0.0)], dtype=np.float64)
    elif isinstance(joints_data, list):
        for item in joints_data:
            if isinstance(item, dict) and "name" in item:
                name = str(item["name"]).upper()
                res[name] = np.array([
                    float(item.get("x", 0.0)),
                    float(item.get("y", 0.0)),
                    float(item.get("z", 0.0)),
                ], dtype=np.float64)
    return res


class AutoTPoseCalibrator:
    """
    Finite State Machine for detecting T-pose and auto-calibrating.
    States:
      - 'idle'       : Performer not in T-pose, monitoring stream
      - 'holding'    : Performer in T-pose, hold timer advancing (0% -> 100%)
      - 'calibrated' : Calibration successfully locked in and active
    """
    def __init__(
        self,
        hold_duration_s: float = 1.2,
        target_height_m: float = 1.75,
        min_elbow_angle_deg: float = 135.0,
        min_knee_angle_deg: float = 135.0,
        max_arm_elevation_ratio: float = 0.45,
    ):
        self.hold_duration = max(0.5, float(hold_duration_s))
        self.target_height = max(1.0, min(2.5, float(target_height_m)))
        self.min_elbow_angle = min_elbow_angle_deg
        self.min_knee_angle = min_knee_angle_deg
        self.max_arm_elevation = max_arm_elevation_ratio

        self.state: str = "idle"
        self.hold_start_time: Optional[float] = None
        self.progress: float = 0.0
        self.pose_buffer: deque = deque(maxlen=60)
        self.calibration_data: Optional[Dict[str, Any]] = None
        self.enabled: bool = True
        self.last_state_change: float = time.time()
        self.just_calibrated: bool = False

    def reset(self):
        """Clears calibration and resets state machine to idle."""
        self.state = "idle"
        self.hold_start_time = None
        self.progress = 0.0
        self.pose_buffer.clear()
        self.calibration_data = None
        self.last_state_change = time.time()
        self.just_calibrated = False
        logger.info("[AutoTPose] Calibration reset to idle.")

    def is_tpose(self, joints: Dict[str, np.ndarray]) -> Tuple[bool, str]:
        """
        Evaluates geometric conditions for a valid T-pose.
        Supports both full-body and upper-body camera framings.
        Returns:
            (is_valid, reason)
        """
        required_upper = [
            "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
            "LEFT_WRIST", "RIGHT_WRIST"
        ]
        for joint in required_upper:
            if joint not in joints:
                return False, f"Missing joint {joint}"

        # 1. Arms straight (elbow angle near 180 degrees)
        l_elbow = _angle_between(joints["LEFT_SHOULDER"], joints["LEFT_ELBOW"], joints["LEFT_WRIST"])
        r_elbow = _angle_between(joints["RIGHT_SHOULDER"], joints["RIGHT_ELBOW"], joints["RIGHT_WRIST"])
        if l_elbow < self.min_elbow_angle:
            return False, f"Left elbow bent ({l_elbow:.1f}° < {self.min_elbow_angle}°)"
        if r_elbow < self.min_elbow_angle:
            return False, f"Right elbow bent ({r_elbow:.1f}° < {self.min_elbow_angle}°)"

        # 2. Arms horizontal (wrist Y close to shoulder Y)
        l_arm = joints["LEFT_WRIST"] - joints["LEFT_SHOULDER"]
        r_arm = joints["RIGHT_WRIST"] - joints["RIGHT_SHOULDER"]
        l_len = np.linalg.norm(l_arm)
        r_len = np.linalg.norm(r_arm)
        if l_len < 0.1 or r_len < 0.1:
            return False, "Arm length degenerate"

        l_slope = abs(l_arm[1]) / l_len
        r_slope = abs(r_arm[1]) / r_len
        if l_slope > self.max_arm_elevation:
            return False, f"Left arm not horizontal (slope {l_slope:.2f})"
        if r_slope > self.max_arm_elevation:
            return False, f"Right arm not horizontal (slope {r_slope:.2f})"

        # 3. Arms extended outward in opposite directions
        if (l_arm[0] * r_arm[0]) >= 0:
            return False, "Arms must extend to opposite sides"

        # 4. Legs straight (if lower body is in frame)
        has_legs = all(k in joints for k in ("LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE"))
        if has_legs:
            l_knee = _angle_between(joints["LEFT_HIP"], joints["LEFT_KNEE"], joints["LEFT_ANKLE"])
            r_knee = _angle_between(joints["RIGHT_HIP"], joints["RIGHT_KNEE"], joints["RIGHT_ANKLE"])
            if l_knee < self.min_knee_angle:
                return False, f"Left knee bent ({l_knee:.1f}°)"
            if r_knee < self.min_knee_angle:
                return False, f"Right knee bent ({r_knee:.1f}°)"

        # 5. Upright Torso (spine vertical along Y axis if hips in frame)
        if "LEFT_HIP" in joints and "RIGHT_HIP" in joints:
            hip_mid = (joints["LEFT_HIP"] + joints["RIGHT_HIP"]) * 0.5
            sh_mid = (joints["LEFT_SHOULDER"] + joints["RIGHT_SHOULDER"]) * 0.5
            torso = sh_mid - hip_mid
            torso_len = np.linalg.norm(torso)
            if torso_len > 0.1:
                torso_up_ratio = torso[1] / torso_len
                if torso_up_ratio < 0.70:
                    return False, f"Torso tilted ({torso_up_ratio:.2f} < 0.70)"

        return True, "Valid T-Pose"

    def update(self, raw_joints: Any, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """
        Updates the calibrator with the latest frame.
        """
        now = timestamp if timestamp is not None else time.time()
        joints = normalize_joints_dict(raw_joints)

        if not self.enabled or len(joints) < 6:
            return self.get_status()

        valid_tpose, reason = self.is_tpose(joints)

        # Compute midpoints if hips/shoulders exist
        if "LEFT_HIP" in joints and "RIGHT_HIP" in joints:
            joints["HIP_MID"] = (joints["LEFT_HIP"] + joints["RIGHT_HIP"]) * 0.5
        if "LEFT_SHOULDER" in joints and "RIGHT_SHOULDER" in joints:
            joints["SHOULDER_MID"] = (joints["LEFT_SHOULDER"] + joints["RIGHT_SHOULDER"]) * 0.5

        if valid_tpose:
            self.pose_buffer.append(joints)
            if self.state in ("idle", "ready"):
                self.state = "holding"
                self.hold_start_time = now
                self.progress = 0.0
                self.last_state_change = now
            elif self.state == "holding":
                start_t = self.hold_start_time if self.hold_start_time is not None else now
                elapsed = now - start_t
                self.progress = min(1.0, elapsed / self.hold_duration)

                # Check if hold duration reached
                if self.progress >= 1.0:
                    self.calibration_data = self._compute_calibration(joints)
                    self.state = "calibrated"  # Remain calibrated while holding this pose
                    self.last_state_change = now
                    self.just_calibrated = True
                    logger.info(
                        f"[AutoTPose] AUTO-CALIBRATION COMPLETE! Locked floor at Y={self.calibration_data['floor_y']:.3f}m, "
                        f"scale factor={self.calibration_data['scale_factor']:.3f}"
                    )
            elif self.state == "calibrated":
                # User is still holding the same T-pose after calibration
                self.progress = 1.0
        else:
            if self.state == "holding":
                # Pose broke before hold time elapsed
                self.state = "idle"
                self.hold_start_time = None
                self.progress = 0.0
                self.pose_buffer.clear()
                self.last_state_change = now
            elif self.state == "calibrated":
                # User relaxed their arms after being calibrated.
                # Transition back to "idle" so they can calibrate again whenever they want,
                # while keeping self.calibration_data intact!
                self.state = "idle"
                self.hold_start_time = None
                self.progress = 0.0
                self.pose_buffer.clear()
                self.last_state_change = now

        status = self.get_status(is_tpose=valid_tpose, reason=reason)
        return status

    def _compute_calibration(self, current_joints: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """
        Calculates rigid bone lengths, floor level, and metric scale.
        """
        samples = list(self.pose_buffer)
        if not samples:
            samples = [current_joints]

        # 1. Bone lengths (median across buffered frames)
        bone_lengths: Dict[str, float] = {}
        for b_name, (j1, j2) in BONE_DEFINITIONS.items():
            dists = []
            for s in samples:
                if j1 in s and j2 in s:
                    d = float(np.linalg.norm(s[j1] - s[j2]))
                    if np.isfinite(d) and d > 0.01:
                        dists.append(d)
            bone_lengths[b_name] = float(np.median(dists)) if dists else 0.0

        # 2. Floor plane estimation (lowest heel / foot Y coordinate)
        heel_ys: List[float] = []
        for s in samples:
            for k in ("LEFT_HEEL", "RIGHT_HEEL", "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX"):
                if k in s:
                    val = float(s[k][1])
                    if np.isfinite(val):
                        heel_ys.append(val)

        # 3. Performer measured height (head/ear to floor)
        head_ys: List[float] = []
        for s in samples:
            for k in ("NOSE", "LEFT_EAR", "RIGHT_EAR", "LEFT_EYE", "RIGHT_EYE"):
                if k in s:
                    val = float(s[k][1])
                    if np.isfinite(val):
                        head_ys.append(val)

        if heel_ys:
            floor_y = float(np.percentile(heel_ys, 10))
            top_y = float(np.percentile(head_ys, 90)) if head_ys else (floor_y + self.target_height)
            measured_height_m = max(0.5, top_y - floor_y + 0.10)
        elif "LEFT_HIP" in current_joints and "RIGHT_HIP" in current_joints:
            # Upper body fallback: hips are ~0.53 of performer height from the ground
            hip_y = float((current_joints["LEFT_HIP"][1] + current_joints["RIGHT_HIP"][1]) * 0.5)
            floor_y = hip_y - (self.target_height * 0.53)
            top_y = float(np.percentile(head_ys, 90)) if head_ys else (floor_y + self.target_height)
            measured_height_m = max(0.5, top_y - floor_y + 0.10)
        else:
            top_y = float(np.percentile(head_ys, 90)) if head_ys else 0.0
            floor_y = top_y - self.target_height
            measured_height_m = self.target_height

        scale_factor = float(self.target_height / measured_height_m)

        # 4. Wingspan (wrist to wrist)
        wingspans = [float(np.linalg.norm(s["LEFT_WRIST"] - s["RIGHT_WRIST"])) for s in samples if "LEFT_WRIST" in s and "RIGHT_WRIST" in s]
        wingspan_m = float(np.median(wingspans)) if wingspans else 0.0

        # 5. Performer Pelvis / Root 3D Position during T-pose (to recenter model to origin)
        root_xs, root_ys, root_zs = [], [], []
        for s in samples:
            if "LEFT_HIP" in s and "RIGHT_HIP" in s:
                root_xs.append(float((s["LEFT_HIP"][0] + s["RIGHT_HIP"][0]) * 0.5))
                root_ys.append(float((s["LEFT_HIP"][1] + s["RIGHT_HIP"][1]) * 0.5))
                root_zs.append(float((s["LEFT_HIP"][2] + s["RIGHT_HIP"][2]) * 0.5))

        root_x = float(np.median(root_xs)) if root_xs else 0.0
        root_y = float(np.median(root_ys)) if root_ys else (floor_y + self.target_height * 0.52)
        root_z = float(np.median(root_zs)) if root_zs else 0.0

        return {
            "calibrated_at": time.time(),
            "samples_count": len(samples),
            "floor_y": round(floor_y, 4),
            "scale_factor": round(scale_factor, 4),
            "target_height_m": self.target_height,
            "measured_height_m": round(measured_height_m, 3),
            "wingspan_m": round(wingspan_m, 3),
            "root_x": round(root_x, 4),
            "root_y": round(root_y, 4),
            "root_z": round(root_z, 4),
            "bone_lengths": {k: round(v, 4) for k, v in bone_lengths.items()},
        }

    def force_calibrate(self) -> Optional[Dict[str, Any]]:
        """Forces calibration immediately using whatever frames are currently buffered."""
        if self.pose_buffer:
            self.calibration_data = self._compute_calibration(self.pose_buffer[-1])
            self.state = "calibrated"
            self.progress = 1.0
            self.last_state_change = time.time()
            self.just_calibrated = True
            return self.calibration_data
        return None

    def get_status(self, is_tpose: bool = False, reason: str = "") -> Dict[str, Any]:
        """Returns serializable dictionary for WebSocket broadcast."""
        was_just_calibrated = self.just_calibrated
        self.just_calibrated = False
        return {
            "state": self.state,
            "progress": round(self.progress, 2),
            "is_tpose": is_tpose,
            "reason": reason if not is_tpose else ("Calibrated" if self.state == "calibrated" else "Holding T-Pose"),
            "has_calibration": self.calibration_data is not None,
            "calibration": self.calibration_data,
            "just_calibrated": was_just_calibrated,
            "recenter": was_just_calibrated,
        }
