"""
Unit tests for RootTracker and global root position translation.
"""
import numpy as np
import pytest

from live_stream_test.root_tracker import RootTracker


def test_monocular_root_estimation():
    tracker = RootTracker(default_performer_height_m=1.75)

    # 2D landmarks for a person spanning Y=100 (ears) to Y=600 (heels) in 1280x720 frame
    landmarks_2d = [
        {"name": "LEFT_EAR", "px_x": 640.0, "px_y": 100.0, "visibility": 0.9},
        {"name": "RIGHT_EAR", "px_x": 600.0, "px_y": 100.0, "visibility": 0.9},
        {"name": "LEFT_HIP", "px_x": 640.0, "px_y": 380.0, "visibility": 0.9},
        {"name": "RIGHT_HIP", "px_x": 600.0, "px_y": 380.0, "visibility": 0.9},
        {"name": "LEFT_HEEL", "px_x": 640.0, "px_y": 600.0, "visibility": 0.9},
        {"name": "RIGHT_HEEL", "px_x": 600.0, "px_y": 600.0, "visibility": 0.9},
    ]

    root = tracker.estimate_monocular_root(landmarks_2d, img_width=1280, img_height=720)
    assert root is not None
    assert len(root) == 3
    # Distance Z should be approximately (1280 * 0.95 * 1.75) / 500 = ~4.25m
    assert 3.5 < root[2] < 5.0
    # X should be close to 0 since hips are near center (620px vs 640px center)
    assert abs(root[0]) < 0.5


def test_root_translation_application():
    tracker = RootTracker(default_performer_height_m=1.75)

    # Fake 3D local joints
    local_joints = [
        {"index": 0, "name": "NOSE", "x": 0.0, "y": 0.8, "z": 0.0, "visibility": 1.0},
        {"index": 11, "name": "LEFT_SHOULDER", "x": 0.2, "y": 0.5, "z": 0.0, "visibility": 1.0},
    ]

    landmarks_2d = [
        {"name": "LEFT_EAR", "px_x": 640.0, "px_y": 100.0, "visibility": 0.9},
        {"name": "LEFT_HIP", "px_x": 640.0, "px_y": 350.0, "visibility": 0.9},
        {"name": "LEFT_HEEL", "px_x": 640.0, "px_y": 600.0, "visibility": 0.9},
    ]

    # Frame 1: sets anchor reference
    out1 = tracker.apply_root_translation(local_joints, landmarks_2d, 1280, 720)
    assert len(out1) == 2
    # Initially at rest position, delta is 0
    assert out1[0]["x"] == pytest.approx(0.0, abs=0.01)

    # Frame 2: performer moves to the right in the camera (px_x moves from 640 to 800)
    shifted_2d = [
        {"name": "LEFT_EAR", "px_x": 800.0, "px_y": 100.0, "visibility": 0.9},
        {"name": "LEFT_HIP", "px_x": 800.0, "px_y": 350.0, "visibility": 0.9},
        {"name": "LEFT_HEEL", "px_x": 800.0, "px_y": 600.0, "visibility": 0.9},
    ]

    out2 = tracker.apply_root_translation(local_joints, shifted_2d, 1280, 720)
    # The X position should shift positively (to the right in 3D world space)
    assert out2[0]["x"] > out1[0]["x"]


def test_root_locked_mode():
    tracker = RootTracker()
    tracker.mode = "root_locked"

    local_joints = [
        {"index": 0, "name": "NOSE", "x": 0.1, "y": 0.8, "z": -0.2, "visibility": 1.0},
    ]
    landmarks_2d = [
        {"name": "LEFT_EAR", "px_x": 900.0, "px_y": 100.0, "visibility": 0.9},
        {"name": "LEFT_HEEL", "px_x": 900.0, "px_y": 600.0, "visibility": 0.9},
    ]

    out = tracker.apply_root_translation(local_joints, landmarks_2d, 1280, 720)
    assert out[0]["x"] == 0.1
    assert out[0]["z"] == -0.2
