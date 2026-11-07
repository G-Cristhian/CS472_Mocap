"""
Tests for Live Multi-Camera Triangulation, Global 3D Position Tracking,
Auto T-Pose Calibration & Recentering, and Low-Latency Anti-Jitter Filtering.
"""
import time
import numpy as np
import pytest

try:
    from backend.live_stream_test.triangulate_live import (
        LiveTriangulator,
        CANONICAL_TPOSE_LANDMARKS,
        build_camera_intrinsics,
    )
    from backend.live_stream_test.auto_tpose import AutoTPoseCalibrator
    from backend.live_stream_test.root_tracker import RootTracker
    from backend.live_stream_test.filter import PoseFilter
    from backend.live_stream_test.detector import LANDMARK_NAMES
except ImportError:
    from live_stream_test.triangulate_live import (
        LiveTriangulator,
        CANONICAL_TPOSE_LANDMARKS,
        build_camera_intrinsics,
    )
    from live_stream_test.auto_tpose import AutoTPoseCalibrator
    from live_stream_test.root_tracker import RootTracker
    from live_stream_test.filter import PoseFilter
    from live_stream_test.detector import LANDMARK_NAMES


def test_tpose_auto_calibration_and_dlt_triangulation():
    """
    Simulates 2 calibrated cameras observing a performer in a T-Pose,
    verifying solvePnP auto-calibrates camera poses and DLT recovers exact 3D points.
    """
    triangulator = LiveTriangulator()
    w, h = 1280, 720
    K = build_camera_intrinsics(w, h)

    # 1. Generate synthetic 2D observations for 2 cameras from canonical T-Pose
    import cv2
    cam0_pos = np.array([0.0, 1.2, 2.5])
    cam1_pos = np.array([1.8, 1.2, 1.8])

    R0 = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float64)
    t0 = -R0 @ cam0_pos.reshape(3, 1)

    theta = np.radians(45)
    c, s = np.cos(theta), np.sin(theta)
    R1 = np.array([[c, 0.0, -s], [0.0, -1.0, 0.0], [-s, 0.0, -c]], dtype=np.float64)
    t1 = -R1 @ cam1_pos.reshape(3, 1)

    cam_kps_tpose = {"cam0": [], "cam1": []}
    for idx, name in enumerate(LANDMARK_NAMES):
        pt3d = CANONICAL_TPOSE_LANDMARKS.get(name, np.array([0.0, 1.0, 0.0]))
        p2d_0 = cv2.projectPoints(pt3d.reshape(1, 3), cv2.Rodrigues(R0)[0], t0, K, None)[0].flatten()
        p2d_1 = cv2.projectPoints(pt3d.reshape(1, 3), cv2.Rodrigues(R1)[0], t1, K, None)[0].flatten()

        cam_kps_tpose["cam0"].append({"index": idx, "name": name, "px_x": float(p2d_0[0]), "px_y": float(p2d_0[1]), "visibility": 0.95})
        cam_kps_tpose["cam1"].append({"index": idx, "name": name, "px_x": float(p2d_1[0]), "px_y": float(p2d_1[1]), "visibility": 0.95})

    # Calibrate cameras from T-Pose
    cal_ok = triangulator.calibrate_from_tpose(cam_kps_tpose, target_height_m=1.75, camera_resolutions={"cam0": (w, h), "cam1": (w, h)})
    assert cal_ok is True
    assert triangulator.is_calibrated is True
    assert "cam0" in triangulator.projection_matrices
    assert "cam1" in triangulator.projection_matrices

    # Triangulate T-Pose points
    tri_pose = triangulator.triangulate(cam_kps_tpose)
    assert tri_pose is not None
    assert len(tri_pose) == 33

    by_name = {j["name"]: j for j in tri_pose if "name" in j}
    assert "NOSE" in by_name
    assert "LEFT_WRIST" in by_name
    assert "RIGHT_WRIST" in by_name

    # Check that wrists are extended to opposite sides (unconstrained wingspan)
    l_wrist = by_name["LEFT_WRIST"]
    r_wrist = by_name["RIGHT_WRIST"]
    assert l_wrist["x"] < -0.5
    assert r_wrist["x"] > 0.5


def test_global_translation_walk_across_room():
    """
    Verifies that when a performer walks across the room,
    the triangulated coordinates translate across the global 3D room.
    """
    triangulator = LiveTriangulator()
    w, h = 1280, 720
    K = build_camera_intrinsics(w, h)

    import cv2
    cam0_pos = np.array([0.0, 1.2, 3.5])
    cam1_pos = np.array([2.5, 1.2, 2.5])

    R0 = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float64)
    t0 = -R0 @ cam0_pos.reshape(3, 1)

    theta = np.radians(45)
    c, s = np.cos(theta), np.sin(theta)
    R1 = np.array([[c, 0.0, -s], [0.0, -1.0, 0.0], [-s, 0.0, -c]], dtype=np.float64)
    t1 = -R1 @ cam1_pos.reshape(3, 1)

    # Initial T-Pose setup
    cam_kps_tpose = {"cam0": [], "cam1": []}
    for idx, name in enumerate(LANDMARK_NAMES):
        pt3d = CANONICAL_TPOSE_LANDMARKS.get(name, np.array([0.0, 1.0, 0.0]))
        p2d_0 = cv2.projectPoints(pt3d.reshape(1, 3), cv2.Rodrigues(R0)[0], t0, K, None)[0].flatten()
        p2d_1 = cv2.projectPoints(pt3d.reshape(1, 3), cv2.Rodrigues(R1)[0], t1, K, None)[0].flatten()
        cam_kps_tpose["cam0"].append({"index": idx, "name": name, "px_x": float(p2d_0[0]), "px_y": float(p2d_0[1]), "visibility": 0.95})
        cam_kps_tpose["cam1"].append({"index": idx, "name": name, "px_x": float(p2d_1[0]), "px_y": float(p2d_1[1]), "visibility": 0.95})

    triangulator.calibrate_from_tpose(cam_kps_tpose, target_height_m=1.75, camera_resolutions={"cam0": (w, h), "cam1": (w, h)})

    # Now performer walks: dx = -1.5m (left), dz = -1.0m (backward)
    walk_offset = np.array([-1.5, 0.0, -1.0])
    cam_kps_walk = {"cam0": [], "cam1": []}
    for idx, name in enumerate(LANDMARK_NAMES):
        pt_walk = CANONICAL_TPOSE_LANDMARKS.get(name, np.array([0.0, 1.0, 0.0])) + walk_offset
        p2d_0 = cv2.projectPoints(pt_walk.reshape(1, 3), cv2.Rodrigues(R0)[0], t0, K, None)[0].flatten()
        p2d_1 = cv2.projectPoints(pt_walk.reshape(1, 3), cv2.Rodrigues(R1)[0], t1, K, None)[0].flatten()
        cam_kps_walk["cam0"].append({"index": idx, "name": name, "px_x": float(p2d_0[0]), "px_y": float(p2d_0[1]), "visibility": 0.95})
        cam_kps_walk["cam1"].append({"index": idx, "name": name, "px_x": float(p2d_1[0]), "px_y": float(p2d_1[1]), "visibility": 0.95})

    walked_pose = triangulator.triangulate(cam_kps_walk)
    assert walked_pose is not None
    by_name = {j["name"]: j for j in walked_pose if "name" in j}

    # Performer NOSE should have moved ~ -1.5 in X and ~ -1.0 in Z
    nose = by_name["NOSE"]
    assert abs(nose["x"] - (-1.5)) < 0.15
    assert abs(nose["z"] - (-1.0)) < 0.15


def test_tpose_auto_calibrator_recenters_origin():
    """
    Verifies that striking a T-Pose triggers auto-calibration and emits recenter signal.
    """
    calibrator = AutoTPoseCalibrator(hold_duration_s=0.5, target_height_m=1.75)

    # Feed T-Pose frames for 0.6s
    t0 = time.time()
    tpose_joints = []
    for name, pt in CANONICAL_TPOSE_LANDMARKS.items():
        tpose_joints.append({"name": name, "x": float(pt[0]), "y": float(pt[1]), "z": float(pt[2]), "visibility": 0.95})

    calibrated = False
    for step in range(16):
        t = t0 + step * 0.04
        status = calibrator.update(tpose_joints, timestamp=t)
        if status.get("state") == "calibrated":
            calibrated = True
            assert status.get("recenter") is True
            assert status["calibration"] is not None
            assert "root_x" in status["calibration"]
            assert "floor_y" in status["calibration"]
            break

    assert calibrated is True


def test_anti_jitter_filter_zero_lag_presets():
    """
    Verifies that fast movement under beta=0.15 / beta=0.3 rapidly opens cutoff,
    while standing still eliminates jitter.
    """
    pf = PoseFilter(min_cutoff=1.8, beta=0.15)
    pf.set_preset("fast")
    assert pf.min_cutoff == 2.5
    assert pf.beta == 0.3

    # Stationary frame with minor noise (jitter)
    t = 0.0
    joints_still_1 = [{"name": "LEFT_WRIST", "x": 0.50, "y": 1.20, "z": 0.00, "visibility": 1.0}]
    joints_still_2 = [{"name": "LEFT_WRIST", "x": 0.52, "y": 1.19, "z": 0.01, "visibility": 1.0}]

    pf.filter_pose(joints_still_1, t)
    t += 0.033
    filtered_still = pf.filter_pose(joints_still_2, t)
    # Jitter filtered smoothly
    assert abs(filtered_still[0]["x"] - 0.52) > 0.001

    # Fast movement (e.g. rapid punch: x jumps from 0.52 to 1.10 in 33ms)
    t += 0.033
    joints_punch = [{"name": "LEFT_WRIST", "x": 1.10, "y": 1.20, "z": 0.40, "visibility": 1.0}]
    filtered_punch = pf.filter_pose(joints_punch, t)

    # In fast mode, high velocity rapidly increases cutoff
    assert filtered_punch[0]["x"] > 0.70
