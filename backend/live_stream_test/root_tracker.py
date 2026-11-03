"""
Global Root Position Estimator and Trajectory Tracker.

Solves the "stuck at origin" problem by estimating global 3D root translation:
  - For single-camera streams: uses pinhole back-projection and scale-from-bounding-box
    to estimate real-world (X, Y, Z) distance and lateral displacement.
  - For multi-camera triangulated streams: preserves calibrated world coordinates.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
import numpy as np


class RootTracker:
    """
    Estimates 3D root position (pelvis translation) from 2D pixel landmarks
    and applies it to 3D world landmarks so the performer moves naturally across the floor.
    """
    def __init__(self, default_performer_height_m: float = 1.75):
        self.target_height = float(default_performer_height_m)
        self.mode: str = "global"  # "global" or "root_locked"

        # Reference anchor (rest pose position when calibrated or started)
        self.reference_pos: Optional[np.ndarray] = None  # (3,) X0, Y0, Z0
        self.smoothed_root: Optional[np.ndarray] = None
        self.alpha: float = 0.25  # Smoothing factor for root displacement

    def reset_anchor(self):
        """Resets reference origin anchor."""
        self.reference_pos = None
        self.smoothed_root = None

    def estimate_monocular_root(
        self,
        landmarks_2d: List[Dict[str, Any]],
        img_width: int,
        img_height: int,
    ) -> Optional[np.ndarray]:
        """
        Estimates (X, Y, Z) in meters relative to camera using pinhole projection.
        """
        if not landmarks_2d or img_width <= 0 or img_height <= 0:
            return None

        # Build lookup by name or index
        pts_px = {}
        for lm in landmarks_2d:
            name = lm.get("name", "")
            vis = lm.get("visibility", 1.0)
            if vis >= 0.3:
                pts_px[name] = np.array([lm.get("px_x", 0.0), lm.get("px_y", 0.0)], dtype=np.float64)

        # Performer vertical span in pixels (ears/head down to heels)
        top_candidates = [pts_px[k] for k in ("LEFT_EAR", "RIGHT_EAR", "NOSE", "LEFT_EYE", "RIGHT_EYE") if k in pts_px]
        bottom_candidates = [pts_px[k] for k in ("LEFT_HEEL", "RIGHT_HEEL", "LEFT_ANKLE", "RIGHT_ANKLE") if k in pts_px]

        if not top_candidates or not bottom_candidates:
            return None

        top_y = min(p[1] for p in top_candidates)
        bottom_y = max(p[1] for p in bottom_candidates)
        h_px = bottom_y - top_y

        if h_px < 30.0:
            return None

        # Estimated camera focal length (~65-70 degree FOV)
        focal_px = img_width * 0.95
        cx = img_width * 0.5
        cy = img_height * 0.5

        # Distance Z = (focal_length * real_height) / pixel_height
        z_m = (focal_px * self.target_height) / h_px

        # Center of hips for X, Y position
        hip_candidates = [pts_px[k] for k in ("LEFT_HIP", "RIGHT_HIP") if k in pts_px]
        if hip_candidates:
            hip_px = np.mean(hip_candidates, axis=0)
        else:
            hip_px = np.array([cx, cy])

        x_m = ((hip_px[0] - cx) * z_m) / focal_px
        # Invert Y so up is positive
        y_m = -((hip_px[1] - cy) * z_m) / focal_px

        return np.array([x_m, y_m, z_m], dtype=np.float64)

    def apply_root_translation(
        self,
        joints_3d: List[Dict[str, Any]],
        landmarks_2d: Optional[List[Dict[str, Any]]],
        img_width: int,
        img_height: int,
        is_triangulated: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Translates root-relative 3D joints into global room space.
        """
        if not joints_3d:
            return []

        # If user explicitly wants root-locked, return joints as-is
        if self.mode == "root_locked":
            return joints_3d

        # In multi-camera triangulated mode, coordinates are ALREADY global in rig space
        if is_triangulated:
            return joints_3d

        if not landmarks_2d:
            return joints_3d

        current_root = self.estimate_monocular_root(landmarks_2d, img_width, img_height)
        if current_root is None:
            return joints_3d

        # Smooth estimated root to prevent jerky camera motion
        if self.smoothed_root is None:
            self.smoothed_root = current_root.copy()
        else:
            self.smoothed_root = (1.0 - self.alpha) * self.smoothed_root + self.alpha * current_root

        # Set initial anchor if not set
        if self.reference_pos is None:
            self.reference_pos = self.smoothed_root.copy()

        # Displacement relative to rest anchor
        dx = float(self.smoothed_root[0] - self.reference_pos[0])
        # Only allow moderate Z displacement (forward/back) to prevent depth noise explosion
        dz = float(np.clip(self.smoothed_root[2] - self.reference_pos[2], -3.0, 3.0))
        # Keep vertical dy stable
        dy = float(np.clip(self.smoothed_root[1] - self.reference_pos[1], -1.0, 1.0))

        translated_joints = []
        for j in joints_3d:
            translated_joints.append({
                "index": j.get("index", 0),
                "name": j.get("name", ""),
                "x": round(float(j.get("x", 0.0)) + dx, 4),
                "y": round(float(j.get("y", 0.0)) + dy, 4),
                "z": round(float(j.get("z", 0.0)) + dz, 4),
                "visibility": j.get("visibility", 1.0),
            })

        return translated_joints
