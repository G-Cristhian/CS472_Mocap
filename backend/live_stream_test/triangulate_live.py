"""
Real-time 3D triangulation for multi-camera live stream mode.
Uses pre-calibrated CameraRig if available, otherwise falls back gracefully.
"""
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np


class LiveTriangulator:
    def __init__(self, calibration_path: Optional[str] = None):
        self.rig = None
        self.camera_group = None
        self.camera_id_map: Dict[str, int] = {}
        if calibration_path:
            self.load_calibration(calibration_path)

    def load_calibration(self, path_str: str) -> bool:
        """
        Loads a calibration.json produced by mocap_pipeline.
        """
        try:
            from mocap_pipeline.io import load_rig
            from mocap_pipeline.stage2_reconstruct.calibrate import rig_to_group

            p = Path(path_str)
            if not p.exists():
                print(f"[LiveTriangulator] Calibration file not found: {p}")
                return False

            self.rig = load_rig(str(p))
            self.camera_group = rig_to_group(self.rig)
            self.camera_id_map = {cam.camera_id: idx for idx, cam in enumerate(self.rig.cameras)}
            print(f"[LiveTriangulator] Successfully loaded calibration with {len(self.rig.cameras)} cameras: {list(self.camera_id_map.keys())}")
            return True
        except Exception as e:
            print(f"[LiveTriangulator] Failed to load calibration: {e}")
            self.rig = None
            self.camera_group = None
            self.camera_id_map = {}
            return False

    @property
    def is_calibrated(self) -> bool:
        return self.camera_group is not None

    def triangulate(self, camera_keypoints: Dict[str, List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """
        camera_keypoints: mapping of camera_id -> list of 33 landmark dicts (with 'px_x', 'px_y', 'visibility')
        Returns list of 33 3D joints in world coordinates, or None if fewer than 2 cameras.
        """
        if not self.is_calibrated or len(camera_keypoints) < 2:
            return None

        # Determine which active cameras match the calibrated rig
        matched = [(cam_id, self.camera_id_map[cam_id]) for cam_id in camera_keypoints if cam_id in self.camera_id_map]
        if len(matched) < 2:
            # Maybe the user named them cam0, cam1 or 0, 1
            # Try index-based matching if IDs don't match exactly
            rig_cam_ids = list(self.camera_id_map.keys())
            active_ids = list(camera_keypoints.keys())
            matched = []
            for i, aid in enumerate(active_ids):
                if i < len(rig_cam_ids):
                    matched.append((aid, i))

        if len(matched) < 2:
            return None

        n_cams = len(self.rig.cameras)
        n_joints = 33
        p2ds = np.full((n_cams, n_joints, 2), np.nan, dtype=np.float64)

        for cam_id, rig_idx in matched:
            kps = camera_keypoints[cam_id]
            for j_idx, kp in enumerate(kps[:n_joints]):
                vis = kp.get("visibility", 1.0)
                if vis >= 0.4:
                    p2ds[rig_idx, j_idx, 0] = kp.get("px_x", 0.0)
                    p2ds[rig_idx, j_idx, 1] = kp.get("px_y", 0.0)

        # Check that at least some joints have 2+ camera views
        valid_views_per_joint = np.sum(~np.isnan(p2ds[:, :, 0]), axis=0)
        if np.max(valid_views_per_joint) < 2:
            return None

        try:
            # aniposelib triangulates (n_cams, n_points, 2) -> (n_points, 3)
            p3d = self.camera_group.triangulate(p2ds)
            result = []
            for j_idx in range(n_joints):
                pt = p3d[j_idx]
                if np.isnan(pt).any():
                    result.append({"index": j_idx, "x": 0.0, "y": 0.0, "z": 0.0, "visibility": 0.0})
                else:
                    result.append({
                        "index": j_idx,
                        "x": float(pt[0]),
                        "y": float(pt[1]),
                        "z": float(pt[2]),
                        "visibility": 1.0,
                    })
            return result
        except Exception as e:
            print(f"[LiveTriangulator] Triangulation error: {e}")
            return None
