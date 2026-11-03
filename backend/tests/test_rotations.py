"""
Stage 3 on frames whose joint rotations can't be solved from the positions.
A real two-camera take crashed export_bvh on one such frame (SciPy refused a
rotation matrix with zero columns), losing the whole BVH; now those joints
keep their previous rotation and the run reports how many frames that was.
"""
import numpy as np

from mocap_pipeline import metrics, run_pipeline
from mocap_pipeline.joints import JOINT_INDEX, RIG_END_SITES, RIG_JOINTS
from mocap_pipeline.stage3_rig import rotations, skeleton
from tests import bvh_reader
from tests.synthetic_scene import Routine, Scene

SHORT = Routine(stand_s=1.0, walk_s=2.0, perform_s=1.0)
ROTATING = [n for n in RIG_JOINTS if n not in RIG_END_SITES]


def export(pose, tmp_path):
    """run_pipeline.export_bvh inside a metrics run. Returns (BVH motion, metrics["rig"])."""
    out, bvh = tmp_path / "out3d.json", tmp_path / "out3d.bvh"
    metrics.start(str(out))
    try:
        run_pipeline.export_bvh(pose, str(bvh))
    finally:
        metrics.finish()
    _, frame_time, motion = bvh_reader.read_bvh(str(bvh))
    assert frame_time > 0
    assert motion.shape == (len(pose.points), 6 + 3 * (len(ROTATING) - 1))
    assert np.isfinite(motion).all()
    assert np.isfinite(np.stack(list(bvh_reader.joint_positions(str(bvh)).values()))).all()
    return motion, metrics.load(str(out))["rig"]


def test_frames_with_no_solvable_rotation_hold_the_previous_one(tmp_path):
    # every joint on one point: no bone has a direction, so no joint can be solved
    pose = Scene(routine=SHORT).truth_pose()
    k = 40
    for f in (0, k):
        pose.points[f] = pose.points[f, JOINT_INDEX["LEFT_HIP"]]

    motion, rig = export(pose, tmp_path)

    rotation = motion[:, 3:]                        # root position is channels 0-2
    assert np.allclose(rotation[0], 0.0, atol=1e-6)        # first frame: the rest pose
    assert np.array_equal(rotation[k], rotation[k - 1])    # later: the previous frame
    assert not np.allclose(rotation[k + 1], rotation[k - 1], atol=1e-3)   # and only that frame
    assert rig["unsolved_frames"] == 2
    held = {name: n for name, n in rig["unsolved_frames_per_joint"].items() if n}
    assert held == {name: 2 for name in rotations.FRAME_RULES}


def test_neck_in_line_with_the_shoulders_is_solved_from_the_hip_line(tmp_path):
    # The take that crashed had frames with one shoulder triangulated metres away, which
    # turns both the shoulder line and the neck (shoulder centre to ear centre) towards it.
    # The Neck's old fallback direction was the neck line itself, so its matrix lost two
    # columns. Here they lie exactly on one line (the z axis, so the arithmetic is exact,
    # as it happened to be in that take).
    pose = Scene(routine=SHORT).truth_pose()
    k = 40
    for name, z in (("RIGHT_SHOULDER", 0.0), ("LEFT_SHOULDER", 10.0), ("LEFT_EAR", 0.25), ("RIGHT_EAR", 0.25)):
        pose.points[k, JOINT_INDEX[name]] = (0.0, 0.0, z)

    rig_positions = skeleton.rig_joint_positions(pose)
    _, local, unsolved = rotations.solve_rotations(rig_positions, None)
    neck, thorax = ROTATING.index("Neck"), ROTATING.index("Thorax")

    assert not unsolved[k, neck]
    assert unsolved[k, thorax]                      # shoulder line and body up are one line too
    R = local[k, neck]
    assert np.allclose(R.T @ R, np.eye(3)) and np.isclose(np.linalg.det(R), 1.0)
    # the Neck's y axis still points along the neck, measured, although its parent was held
    world = np.eye(3)
    for name in ("Hip", "Spine", "Thorax", "Neck"):
        world = world @ local[k, ROTATING.index(name)]
    assert np.allclose(world[:, 1], (0.0, 0.0, -1.0))

    _, rig = export(pose, tmp_path)
    assert rig["unsolved_frames"] == 1
    assert rig["unsolved_frames_per_joint"]["Thorax"] == 1 and rig["unsolved_frames_per_joint"]["Neck"] == 0
