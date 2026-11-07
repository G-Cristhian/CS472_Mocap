"""
Real-time 3D triangulation for multi-camera live stream mode.

Supports:
1. Auto-calibration from live T-Pose (using cv2.solvePnP across active cameras).
2. Default geometric rig layout so triangulation runs immediately with 2+ cameras.
3. Pre-calibrated CameraRig if available (from offline mocap_pipeline calibration.json).
4. Sub-millisecond Direct Linear Transformation (DLT) triangulation for 33 joints.
5. Global 3D coordinate tracking: performer can walk freely in the room and the 3D
   model follows them across the space without being stuck at the origin.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

from .detector import LANDMARK_NAMES

logger = logging.getLogger("live_triangulator")

# Canonical 3D landmarks for a 1.75m performer standing in a standard T-pose at the origin
# Head at Y~1.65, Hips at Y~0.90, Feet on floor at Y~0.0, Wingspan ~ 1.75m
CANONICAL_TPOSE_LANDMARKS: Dict[str, np.ndarray] = {
    "NOSE": np.array([0.0, 1.65, 0.0]),
    "LEFT_EYE": np.array([-0.035, 1.68, 0.0]),
    "RIGHT_EYE": np.array([0.035, 1.68, 0.0]),
    "LEFT_EAR": np.array([-0.08, 1.66, 0.0]),
    "RIGHT_EAR": np.array([0.08, 1.66, 0.0]),
    "LEFT_SHOULDER": np.array([-0.20, 1.42, 0.0]),
    "RIGHT_SHOULDER": np.array([0.20, 1.42, 0.0]),
    "LEFT_ELBOW": np.array([-0.48, 1.42, 0.0]),
    "RIGHT_ELBOW": np.array([0.48, 1.42, 0.0]),
    "LEFT_WRIST": np.array([-0.75, 1.42, 0.0]),
    "RIGHT_WRIST": np.array([0.75, 1.42, 0.0]),
    "LEFT_HIP": np.array([-0.11, 0.88, 0.0]),
    "RIGHT_HIP": np.array([0.11, 0.88, 0.0]),
    "LEFT_KNEE": np.array([-0.11, 0.48, 0.0]),
    "RIGHT_KNEE": np.array([0.11, 0.48, 0.0]),
    "LEFT_ANKLE": np.array([-0.11, 0.08, 0.0]),
    "RIGHT_ANKLE": np.array([0.11, 0.08, 0.0]),
    "LEFT_HEEL": np.array([-0.11, 0.04, -0.05]),
    "RIGHT_HEEL": np.array([0.11, 0.04, -0.05]),
    "LEFT_FOOT_INDEX": np.array([-0.11, 0.02, 0.12]),
    "RIGHT_FOOT_INDEX": np.array([0.11, 0.02, 0.12]),
}

PARENT_JOINTS: Dict[int, int] = {
    1: 0, 2: 1, 3: 2, 4: 0, 5: 4, 6: 5, 7: 3, 8: 6,
    9: 10, 10: 9,
    11: 12, 12: 11,
    13: 11, 14: 12, 15: 13, 16: 14,
    17: 15, 18: 16, 19: 15, 20: 16, 21: 15, 22: 16,
    23: 11, 24: 12,
    25: 23, 26: 24, 27: 25, 28: 26, 29: 27, 30: 28, 31: 27, 32: 28,
}


def build_camera_intrinsics(width: int, height: int) -> np.ndarray:
    """Estimates pinhole intrinsic matrix K (~65-70 deg FOV)."""
    w = max(width, 320)
    h = max(height, 240)
    f = float(w * 0.95)
    return np.array([
        [f, 0.0, w * 0.5],
        [0.0, f, h * 0.5],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)


def solve_dlt_point(P_list: List[np.ndarray], uv_list: List[Tuple[float, float]]) -> Optional[np.ndarray]:
    """
    Sub-millisecond multi-camera Direct Linear Transformation (DLT).
    Given N >= 2 projection matrices P (3x4) and (u, v) points, solves for (X, Y, Z).
    """
    if len(P_list) < 2 or len(P_list) != len(uv_list):
        return None

    A = []
    for P, (u, v) in zip(P_list, uv_list):
        A.append(u * P[2] - P[0])
        A.append(v * P[2] - P[1])
    A = np.asarray(A, dtype=np.float64)

    # Solve A X = 0 using eigenvector of A^T A (4x4 matrix)
    try:
        AtA = A.T @ A
        _, vh = np.linalg.eigh(AtA)
        X = vh[:, 0]
        if abs(X[3]) < 1e-8:
            return None
        return X[:3] / X[3]
    except Exception:
        return None


class LiveTriangulator:
    """
    High-performance real-time 3D pose triangulator.
    Reconstructs global 3D motion so the model follows the user across the room.
    """
    def __init__(self, calibration_path: Optional[str] = None):
        self.rig = None
        self.camera_group = None
        self.camera_id_map: Dict[str, int] = {}
        self.calibration_path: Optional[str] = None

        # Live projection matrices for active cameras: cam_id -> 3x4 P matrix
        self.projection_matrices: Dict[str, np.ndarray] = {}
        self.camera_intrinsics: Dict[str, np.ndarray] = {}
        self.camera_poses: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}  # cam_id -> (R, t)

        # Origin offset to recenter performer to (0, 0, 0)
        self.origin_offset = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.is_auto_calibrated: bool = False
        self.last_triangulated_pose: Optional[List[Dict[str, Any]]] = None

        if calibration_path:
            self.load_calibration(calibration_path)

    def load_calibration(self, path_str: str) -> bool:
        """
        Loads a pre-calibrated rig JSON file produced by mocap_pipeline.
        """
        try:
            from mocap_pipeline.io import load_rig
            from mocap_pipeline.stage2_reconstruct.calibrate import rig_to_group

            p = Path(path_str)
            if not p.exists():
                logger.warning(f"[LiveTriangulator] Calibration file not found: {p}")
                return False

            self.rig = load_rig(str(p))
            self.camera_group = rig_to_group(self.rig)
            self.camera_id_map = {cam.camera_id: idx for idx, cam in enumerate(self.rig.cameras)}
            self.calibration_path = str(p.resolve())
            logger.info(f"[LiveTriangulator] Loaded calibration with {len(self.rig.cameras)} cameras: {list(self.camera_id_map.keys())}")
            return True
        except Exception as e:
            logger.warning(f"[LiveTriangulator] Failed to load calibration: {e}")
            self.rig = None
            self.camera_group = None
            self.camera_id_map = {}
            return False

    @property
    def is_calibrated(self) -> bool:
        return (self.camera_group is not None) or (len(self.projection_matrices) >= 2)

    def initialize_default_camera_layout(self, active_cameras: List[str], width: int = 1280, height: int = 720):
        """
        Establishes default camera geometry so 2+ cameras can triangulate immediately.
        Camera 0: Front facing (0, 1.2, 2.5) pointing at (0, 1.0, 0)
        Camera 1: Angled +45 deg (1.8, 1.2, 1.8)
        Camera 2: Angled -45 deg (-1.8, 1.2, 1.8)
        Camera 3: Side view (2.5, 1.2, 0)
        """
        if not active_cameras:
            return

        K = build_camera_intrinsics(width, height)
        angles_and_positions = [
            (0.0, np.array([0.0, 1.2, 2.5])),
            (45.0, np.array([1.8, 1.2, 1.8])),
            (-45.0, np.array([-1.8, 1.2, 1.8])),
            (90.0, np.array([2.5, 1.2, 0.0])),
            (-90.0, np.array([-2.5, 1.2, 0.0])),
        ]

        for idx, cam_id in enumerate(active_cameras):
            angle_deg, pos = angles_and_positions[idx % len(angles_and_positions)]
            theta = np.radians(angle_deg)
            c, s = np.cos(theta), np.sin(theta)

            # Rotation matrix: look at performer origin, Y-up world to OpenCV (Y-down, Z-forward)
            R = np.array([
                [c, 0.0, -s],
                [0.0, -1.0, 0.0],
                [-s, 0.0, -c],
            ], dtype=np.float64)

            # Camera translation t = -R * C
            t = -R @ pos.reshape(3, 1)

            P = K @ np.hstack([R, t])
            self.projection_matrices[cam_id] = P
            self.camera_intrinsics[cam_id] = K
            self.camera_poses[cam_id] = (R, t)

        logger.info(f"[LiveTriangulator] Initialized default multi-view geometry for cameras: {active_cameras}")

    def calibrate_from_tpose(
        self,
        camera_landmarks: Dict[str, List[Dict[str, Any]]],
        target_height_m: float = 1.75,
        camera_resolutions: Optional[Dict[str, Tuple[int, int]]] = None,
    ) -> bool:
        """
        Auto-calibrates camera extrinsics (position and orientation in the room)
        directly from the user's detected T-Pose using OpenCV solvePnP.
        Recenters the 3D room origin to the performer's location.
        """
        if len(camera_landmarks) < 2:
            return False

        scale = max(1.0, min(2.5, target_height_m)) / 1.75
        scaled_canonical = {k: v * scale for k, v in CANONICAL_TPOSE_LANDMARKS.items()}

        calibrated_count = 0
        new_proj_matrices = {}
        new_poses = {}

        for cam_id, kps in camera_landmarks.items():
            if not kps:
                continue

            by_name = {kp.get("name", ""): kp for kp in kps if kp.get("visibility", 0.0) >= 0.4}

            obj_pts = []
            img_pts = []

            for name, canon_3d in scaled_canonical.items():
                if name in by_name:
                    kp = by_name[name]
                    px_x = kp.get("px_x", 0.0)
                    px_y = kp.get("px_y", 0.0)
                    if px_x > 0 or px_y > 0:
                        obj_pts.append(canon_3d)
                        img_pts.append([px_x, px_y])

            if len(obj_pts) < 8:
                continue

            obj_arr = np.asarray(obj_pts, dtype=np.float64)
            img_arr = np.asarray(img_pts, dtype=np.float64)

            # Get image resolution
            if camera_resolutions and cam_id in camera_resolutions:
                width, height = camera_resolutions[cam_id]
            else:
                max_x = max(img_arr[:, 0].max(), 640.0)
                max_y = max(img_arr[:, 1].max(), 480.0)
                width = 1280 if max_x > 640 else 640
                height = 720 if max_y > 480 else 480

            K = build_camera_intrinsics(width, height)

            try:
                # Solve camera pose R, t
                success, rvec, tvec = cv2.solvePnP(
                    obj_arr,
                    img_arr,
                    K,
                    None,
                    flags=cv2.SOLVEPNP_EPNP,
                )
                if not success:
                    success, rvec, tvec = cv2.solvePnP(
                        obj_arr,
                        img_arr,
                        K,
                        None,
                        flags=cv2.SOLVEPNP_ITERATIVE,
                    )

                if success:
                    R, _ = cv2.Rodrigues(rvec)
                    t = tvec.reshape(3, 1)
                    P = K @ np.hstack([R, t])

                    new_proj_matrices[cam_id] = P
                    new_poses[cam_id] = (R, t)
                    self.camera_intrinsics[cam_id] = K
                    calibrated_count += 1
            except Exception as e:
                logger.warning(f"[LiveTriangulator] solvePnP failed on camera {cam_id}: {e}")

        if calibrated_count >= 2:
            self.projection_matrices.update(new_proj_matrices)
            self.camera_poses.update(new_poses)
            self.is_auto_calibrated = True
            # Performer standing in T-pose is at the origin
            self.origin_offset = np.array([0.0, 0.0, 0.0], dtype=np.float64)
            logger.info(f"[LiveTriangulator] T-Pose calibration SUCCESS! Calibrated {calibrated_count} cameras.")
            return True

        return False

    def recenter(self, root_position: Optional[np.ndarray] = None):
        """Recenters world coordinates to the specified root position or last triangulated root."""
        if root_position is not None:
            self.origin_offset = np.asarray(root_position, dtype=np.float64).copy()
        elif self.last_triangulated_pose:
            by_name = {j["name"]: j for j in self.last_triangulated_pose if "name" in j}
            l_hip = by_name.get("LEFT_HIP")
            r_hip = by_name.get("RIGHT_HIP")
            if l_hip and r_hip:
                rx = (l_hip["x"] + r_hip["x"]) * 0.5 + self.origin_offset[0]
                rz = (l_hip["z"] + r_hip["z"]) * 0.5 + self.origin_offset[2]
                self.origin_offset[0] = rx
                self.origin_offset[2] = rz

    def triangulate(
        self,
        camera_keypoints: Dict[str, List[Dict[str, Any]]],
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Triangulates 33 pose landmarks from active cameras.
        Returns unconstrained, metric 3D joints in real-world space.
        """
        active_ids = [cid for cid, kps in camera_keypoints.items() if kps and len(kps) > 0]
        if len(active_ids) < 2:
            return None

        # 1. Use loaded offline CameraRig if available
        if self.camera_group is not None:
            return self._triangulate_with_rig(camera_keypoints)

        # 2. If no projection matrices exist for these cameras yet, initialize default geometry
        missing = [cid for cid in active_ids if cid not in self.projection_matrices]
        if missing or len(self.projection_matrices) < 2:
            self.initialize_default_camera_layout(active_ids)

        n_joints = 33
        triangulated: List[Dict[str, Any]] = []

        # Build index/name lookup for each camera
        cam_lookups: Dict[str, Dict[Any, Dict[str, Any]]] = {}
        for cid in active_ids:
            cam_lookups[cid] = {}
            for idx, kp in enumerate(camera_keypoints[cid]):
                kp_idx = kp.get("index", idx)
                cam_lookups[cid][kp_idx] = kp
                if "name" in kp:
                    cam_lookups[cid][str(kp["name"]).upper()] = kp

        for j_idx in range(n_joints):
            name = LANDMARK_NAMES[j_idx] if j_idx < len(LANDMARK_NAMES) else f"JOINT_{j_idx}"

            P_list = []
            uv_list = []
            vis_list = []

            for cid in active_ids:
                if cid not in self.projection_matrices:
                    continue
                lookup = cam_lookups.get(cid, {})
                kp = lookup.get(j_idx) or lookup.get(name)
                if kp is not None:
                    vis = float(kp.get("visibility", 1.0))
                    if vis >= 0.35 and (kp.get("px_x", 0.0) > 0 or kp.get("px_y", 0.0) > 0):
                        P_list.append(self.projection_matrices[cid])
                        uv_list.append((float(kp["px_x"]), float(kp["px_y"])))
                        vis_list.append(vis)

            if len(P_list) >= 2:
                pt3d = solve_dlt_point(P_list, uv_list)
                if pt3d is not None and np.all(np.isfinite(pt3d)):
                    # Subtract origin offset so calibrated T-pose sits at origin
                    wx = float(pt3d[0] - self.origin_offset[0])
                    wy = float(pt3d[1] - self.origin_offset[1])
                    wz = float(pt3d[2] - self.origin_offset[2])
                    avg_vis = float(np.mean(vis_list))
                    triangulated.append({
                        "index": j_idx,
                        "name": name,
                        "x": round(wx, 4),
                        "y": round(wy, 4),
                        "z": round(wz, 4),
                        "visibility": round(avg_vis, 3),
                    })
                    continue

            # Fallback for single-view or occluded joint: inherit from parent joint
            parent_idx = PARENT_JOINTS.get(j_idx)
            if parent_idx is not None and parent_idx < len(triangulated) and triangulated[parent_idx]["visibility"] > 0.2:
                parent_pt = triangulated[parent_idx]
                triangulated.append({
                    "index": j_idx,
                    "name": name,
                    "x": parent_pt["x"],
                    "y": parent_pt["y"] - 0.05,
                    "z": parent_pt["z"],
                    "visibility": 0.2,
                })
            else:
                triangulated.append({
                    "index": j_idx,
                    "name": name,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "visibility": 0.0,
                })

        # Check that we recovered a meaningful skeleton (e.g. at least 6 joints)
        valid_count = sum(1 for j in triangulated if j["visibility"] > 0.3)
        if valid_count >= 6:
            self.last_triangulated_pose = triangulated
            return triangulated

        return None

    def _triangulate_with_rig(self, camera_keypoints: Dict[str, List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """Triangulates using pre-calibrated aniposelib CameraGroup."""
        matched = [(cam_id, self.camera_id_map[cam_id]) for cam_id in camera_keypoints if cam_id in self.camera_id_map]
        if len(matched) < 2:
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
                if vis >= 0.35:
                    p2ds[rig_idx, j_idx, 0] = kp.get("px_x", 0.0)
                    p2ds[rig_idx, j_idx, 1] = kp.get("px_y", 0.0)

        valid_views_per_joint = np.sum(~np.isnan(p2ds[:, :, 0]), axis=0)
        if np.max(valid_views_per_joint) < 2:
            return None

        try:
            p3d = self.camera_group.triangulate(p2ds)
            result = []
            for j_idx in range(n_joints):
                name = LANDMARK_NAMES[j_idx] if j_idx < len(LANDMARK_NAMES) else f"JOINT_{j_idx}"
                pt = p3d[j_idx]
                if np.isnan(pt).any():
                    result.append({"index": j_idx, "name": name, "x": 0.0, "y": 0.0, "z": 0.0, "visibility": 0.0})
                else:
                    result.append({
                        "index": j_idx,
                        "name": name,
                        "x": float(pt[0] - self.origin_offset[0]),
                        "y": float(pt[1] - self.origin_offset[1]),
                        "z": float(pt[2] - self.origin_offset[2]),
                        "visibility": 1.0,
                    })
            self.last_triangulated_pose = result
            return result
        except Exception as e:
            logger.warning(f"[LiveTriangulator] Rig triangulation error: {e}")
            return None
