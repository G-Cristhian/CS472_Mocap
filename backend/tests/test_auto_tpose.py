"""
Unit tests for the AutoTPoseCalibrator module.
Verifies geometric rules, state machine transitions, and calibration calculations.
"""
import numpy as np
import pytest

from live_stream_test.auto_tpose import AutoTPoseCalibrator, normalize_joints_dict


def make_perfect_tpose_joints(heel_y: float = -0.85, performer_height: float = 1.70) -> dict:
    """
    Constructs a geometrically perfect T-pose in meters (Y-up, X-right, Z-depth).
    """
    # Floor is at heel_y
    ankle_y = heel_y + 0.05
    knee_y = ankle_y + 0.40
    hip_y = knee_y + 0.45
    shoulder_y = hip_y + 0.50
    head_y = shoulder_y + 0.25

    return {
        "NOSE": np.array([0.0, head_y, 0.0]),
        "LEFT_EYE": np.array([0.03, head_y + 0.03, 0.0]),
        "RIGHT_EYE": np.array([-0.03, head_y + 0.03, 0.0]),
        "LEFT_EAR": np.array([0.07, head_y, 0.0]),
        "RIGHT_EAR": np.array([-0.07, head_y, 0.0]),
        "LEFT_SHOULDER": np.array([0.20, shoulder_y, 0.0]),
        "RIGHT_SHOULDER": np.array([-0.20, shoulder_y, 0.0]),
        "LEFT_ELBOW": np.array([0.45, shoulder_y, 0.0]),
        "RIGHT_ELBOW": np.array([-0.45, shoulder_y, 0.0]),
        "LEFT_WRIST": np.array([0.70, shoulder_y, 0.0]),
        "RIGHT_WRIST": np.array([-0.70, shoulder_y, 0.0]),
        "LEFT_HIP": np.array([0.12, hip_y, 0.0]),
        "RIGHT_HIP": np.array([-0.12, hip_y, 0.0]),
        "LEFT_KNEE": np.array([0.12, knee_y, 0.0]),
        "RIGHT_KNEE": np.array([-0.12, knee_y, 0.0]),
        "LEFT_ANKLE": np.array([0.12, ankle_y, 0.0]),
        "RIGHT_ANKLE": np.array([-0.12, ankle_y, 0.0]),
        "LEFT_HEEL": np.array([0.12, heel_y, 0.0]),
        "RIGHT_HEEL": np.array([-0.12, heel_y, 0.0]),
        "LEFT_FOOT_INDEX": np.array([0.12, heel_y, 0.15]),
        "RIGHT_FOOT_INDEX": np.array([-0.12, heel_y, 0.15]),
    }


def test_perfect_tpose_is_detected():
    calibrator = AutoTPoseCalibrator()
    joints = make_perfect_tpose_joints()
    is_valid, reason = calibrator.is_tpose(joints)
    assert is_valid is True
    assert "Valid" in reason


def test_bent_arms_rejected():
    calibrator = AutoTPoseCalibrator()
    joints = make_perfect_tpose_joints()
    # Bend left elbow 90 degrees
    joints["LEFT_WRIST"] = np.array([0.45, joints["LEFT_ELBOW"][1] + 0.25, 0.0])
    is_valid, reason = calibrator.is_tpose(joints)
    assert is_valid is False
    assert "elbow" in reason.lower()


def test_arms_down_rejected():
    calibrator = AutoTPoseCalibrator()
    joints = make_perfect_tpose_joints()
    # Put arms down by sides
    joints["LEFT_ELBOW"] = np.array([0.22, joints["LEFT_SHOULDER"][1] - 0.25, 0.0])
    joints["LEFT_WRIST"] = np.array([0.22, joints["LEFT_SHOULDER"][1] - 0.50, 0.0])
    is_valid, reason = calibrator.is_tpose(joints)
    assert is_valid is False
    assert "horizontal" in reason.lower()


def test_bent_knees_rejected():
    calibrator = AutoTPoseCalibrator()
    joints = make_perfect_tpose_joints()
    # Squat: bend knees forward
    joints["LEFT_KNEE"] = np.array([0.12, joints["LEFT_KNEE"][1], 0.30])
    is_valid, reason = calibrator.is_tpose(joints)
    assert is_valid is False
    assert "knee" in reason.lower()


def test_tpose_hold_advancement_and_calibration():
    calibrator = AutoTPoseCalibrator(hold_duration_s=1.0, target_height_m=1.75)
    joints = make_perfect_tpose_joints(heel_y=-0.80)

    # Frame 1 at t=0.0 -> starts holding
    res1 = calibrator.update(joints, timestamp=100.0)
    assert res1["state"] == "holding"
    assert res1["progress"] == 0.0
    assert res1["has_calibration"] is False

    # Frame 2 at t=0.5 -> 50% progress
    res2 = calibrator.update(joints, timestamp=100.5)
    assert res2["state"] == "holding"
    assert res2["progress"] == pytest.approx(0.5, abs=0.05)

    # Frame 3 at t=1.1 -> calibrated!
    res3 = calibrator.update(joints, timestamp=101.1)
    assert res3["state"] == "calibrated"
    assert res3["progress"] == 1.0
    assert res3["has_calibration"] is True

    cal = res3["calibration"]
    assert cal is not None
    assert "floor_y" in cal
    assert cal["floor_y"] == pytest.approx(-0.80, abs=0.05)
    assert "bone_lengths" in cal
    assert cal["bone_lengths"]["upper_arm_left"] == pytest.approx(0.25, abs=0.02)
    assert cal["bone_lengths"]["forearm_left"] == pytest.approx(0.25, abs=0.02)
    assert cal["wingspan_m"] == pytest.approx(1.40, abs=0.05)


def test_pose_break_resets_holding():
    calibrator = AutoTPoseCalibrator(hold_duration_s=1.0)
    valid_joints = make_perfect_tpose_joints()

    # Hold for 0.5s
    calibrator.update(valid_joints, timestamp=10.0)
    res = calibrator.update(valid_joints, timestamp=10.5)
    assert res["state"] == "holding"

    # Break pose
    broken_joints = make_perfect_tpose_joints()
    broken_joints["LEFT_WRIST"] = np.array([0.0, 0.0, 0.0])  # dropped arm
    res_break = calibrator.update(broken_joints, timestamp=10.6)

    assert res_break["state"] == "idle"
    assert res_break["progress"] == 0.0


def test_reset_and_force_calibration():
    calibrator = AutoTPoseCalibrator(hold_duration_s=1.0)
    joints = make_perfect_tpose_joints()

    # Push 1 frame and force calibrate
    calibrator.update(joints, timestamp=1.0)
    cal = calibrator.force_calibrate()
    assert cal is not None
    assert calibrator.state == "calibrated"

    calibrator.reset()
    assert calibrator.state == "idle"
    assert calibrator.calibration_data is None
