"""
Stage 3a: turn 33 loose points into a skeleton with fixed bone lengths.

Input : cleaned Pose3D.
Output: rig joint positions per frame + one constant length per bone.
"""
from __future__ import annotations

from ..schemas import Pose3D


def rig_joint_positions(pose: Pose3D):
    """
    TODO: for each entry of joints.RIG_JOINT_SOURCES, average the listed
    MediaPipe joints. Return an array (F, len(RIG_JOINTS), 3) in RIG_JOINTS
    order.
    """
    raise NotImplementedError


def bone_lengths(rig_positions):
    """
    TODO: for each joint with a parent (joints.RIG_PARENTS), take the MEDIAN
    over all frames of its distance to the parent. Average the left and right
    versions of a bone so the skeleton is symmetric.
    Return {joint_name: length_m}.
    """
    raise NotImplementedError


def rest_pose_offsets(lengths):
    """
    The T-pose the rig file declares: each joint's offset from its parent.

    TODO: choose a direction per bone (spine and head up +Y, arms out along
    +X / -X, legs down -Y, toes forward +Z) and multiply by the bone length.
    Return {joint_name: (x, y, z)}. BVH wants centimetres by convention;
    convert in bvh_writer, not here.
    """
    raise NotImplementedError
