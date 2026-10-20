"""
The detected top of the head (joints.HEAD_TOP, RTMPose only) in the scale
step and the rig's Head, with the ear-based estimates as the fallback: for
MediaPipe, in frames where it is missing, and with
config.USE_DETECTED_HEAD_TOP off. Checked on the synthetic performer's true
pose, so no calibration runs.
"""
import numpy as np
import pytest

from mocap_pipeline import config
from mocap_pipeline.joints import JOINT_INDEX, RIG_JOINTS
from mocap_pipeline.schemas import Pose3D
from mocap_pipeline.stage2_reconstruct import scale_floor
from mocap_pipeline.stage3_rig import bvh_writer, rotations, skeleton
from tests import bvh_reader
from tests.synthetic_scene import PERFORMER_HEIGHT_M, Routine, Scene

SHORT = Routine(stand_s=2.0, walk_s=6.0, perform_s=3.0)
TOP = JOINT_INDEX["HEAD_TOP"]
HEAD = RIG_JOINTS.index("Head")
UNITS = 0.37                     # rig units per metre before the scale step


def unscaled(extra_joints):
    """The true pose in arbitrary units, as the rough triangulation hands it to the scale step."""
    pose = Scene(routine=SHORT, extra_joints=extra_joints).truth_pose()
    return Pose3D(fps=pose.fps, points=pose.points * UNITS, num_views=pose.num_views)


# The scene's heel-to-ear distance is 1.60 m. With a deliberately wrong
# HEAD_TOP_ABOVE_EARS_M of 0.20 the ear rule takes it for 1.75 - 0.20 - 0.03 =
# 1.52 m and gets the scale 5% wrong; the head-top rule does not use it.
WRONG_EAR_OFFSET = 0.20
EAR_RULE_SCALE = (PERFORMER_HEIGHT_M - WRONG_EAR_OFFSET - config.HEEL_ABOVE_FLOOR_M) / 1.60 / UNITS


@pytest.fixture
def wrong_ear_offset(monkeypatch):
    monkeypatch.setattr(config, "HEAD_TOP_ABOVE_EARS_M", WRONG_EAR_OFFSET)


def test_height_is_measured_to_the_detected_head_top(wrong_ear_offset):
    scale = scale_floor.scale_factor_from_height(unscaled(extra_joints=True), PERFORMER_HEIGHT_M)
    assert scale == pytest.approx(1 / UNITS, rel=1e-3)


def test_mediapipe_takes_measure_to_the_ears(wrong_ear_offset):
    scale = scale_floor.scale_factor_from_height(unscaled(extra_joints=False), PERFORMER_HEIGHT_M)
    assert scale == pytest.approx(EAR_RULE_SCALE, rel=1e-3)


def test_switched_off_the_head_top_is_ignored(wrong_ear_offset, monkeypatch):
    monkeypatch.setattr(config, "USE_DETECTED_HEAD_TOP", False)
    scale = scale_floor.scale_factor_from_height(unscaled(extra_joints=True), PERFORMER_HEIGHT_M)
    assert scale == pytest.approx(EAR_RULE_SCALE, rel=1e-3)


def test_a_head_top_seen_in_too_few_upright_frames_falls_back_to_the_ears(wrong_ear_offset):
    pose = unscaled(extra_joints=True)
    pose.points[config.MIN_UPRIGHT_FRAMES - 1:, TOP] = np.nan
    scale = scale_floor.scale_factor_from_height(pose, PERFORMER_HEIGHT_M)
    assert scale == pytest.approx(EAR_RULE_SCALE, rel=1e-3)


# ---- the rig's Head ------------------------------------------------------------------

def test_rig_head_is_the_detected_head_top():
    pose = Scene(routine=SHORT, extra_joints=True).truth_pose()
    rig = skeleton.rig_joint_positions(pose)
    np.testing.assert_array_equal(rig[:, HEAD], pose.points[:, TOP])


def test_rig_head_falls_back_to_the_estimate_where_the_head_top_is_missing():
    pose = Scene(routine=SHORT, extra_joints=True).truth_pose()
    estimate = skeleton.rig_joint_positions(Scene(routine=SHORT).truth_pose())[:, HEAD]
    # the estimate is another point: 2/3 of the shoulder-to-ear distance above the ears, not 12 cm
    assert np.linalg.norm(estimate - pose.points[:, TOP], axis=1).min() > 0.01
    pose.points[100:150, TOP] = np.nan
    rig = skeleton.rig_joint_positions(pose)
    np.testing.assert_allclose(rig[100:150, HEAD], estimate[100:150], atol=1e-12)
    np.testing.assert_array_equal(rig[:100, HEAD], pose.points[:100, TOP])


def test_switched_off_the_rig_head_is_the_estimate(monkeypatch):
    monkeypatch.setattr(config, "USE_DETECTED_HEAD_TOP", False)
    with_top = skeleton.rig_joint_positions(Scene(routine=SHORT, extra_joints=True).truth_pose())
    without = skeleton.rig_joint_positions(Scene(routine=SHORT).truth_pose())
    np.testing.assert_allclose(with_top, without, atol=1e-12)


def test_only_the_head_uses_an_extra_joint():
    with_extras = skeleton.rig_joint_positions(Scene(routine=SHORT, extra_joints=True).truth_pose())
    without = skeleton.rig_joint_positions(Scene(routine=SHORT).truth_pose())
    others = [j for j in range(len(RIG_JOINTS)) if j != HEAD]
    np.testing.assert_allclose(with_extras[:, others], without[:, others], atol=1e-12)


def test_bvh_head_end_site_is_the_detected_head_top(tmp_path):
    pose = Scene(routine=SHORT, extra_joints=True).truth_pose()
    rig_pos = skeleton.rig_joint_positions(pose)
    offsets = skeleton.rest_pose_offsets(skeleton.bone_lengths(rig_pos))
    root, local = rotations.solve_rotations(rig_pos, offsets)
    path = tmp_path / "head_top.bvh"
    bvh_writer.write_bvh(str(path), offsets, root, rotations.to_euler_degrees(local, bvh_writer.ROTATION_ORDER),
                         pose.fps)
    fk = bvh_reader.joint_positions(str(path))
    assert np.linalg.norm(fk["Neck_end"] - pose.points[:, TOP], axis=1).max() < 1e-4
