"""
Stage 3b: positions -> joint rotations.

Rig files store, per frame, how each joint is ROTATED relative to its parent
plus the root's position. This is the hardest part of stage 3.

Input : rig joint positions (F, R, 3) and the rest pose offsets.
Output: root position (F, 3) and local rotations per joint per frame.
"""
from __future__ import annotations


def bone_rotation(rest_direction, current_direction):
    """
    Smallest rotation taking one unit vector onto another.
    TODO: axis = cross product, angle = arccos of dot product; return a
    quaternion or 3x3 matrix. Handle the parallel and opposite cases.
    """
    raise NotImplementedError


def solve_rotations(rig_positions, rest_offsets):
    """
    TODO:
      1. Root (Hips): build a full orientation from two directions, e.g. hip
         line (left hip -> right hip) and spine (hips -> chest), so the body's
         facing direction is captured. Root position = Hips position.
      2. Walk joints in joints.RIG_JOINTS order (parents first). For each
         joint with a child: world rotation = bone_rotation(rest direction of
         the child offset, observed direction to the child).
      3. Local rotation = inverse(parent world rotation) * world rotation.
      4. Twist along a bone cannot be recovered from two points. Leave it at
         zero for limbs for now; note it as a known limitation.
      5. Check for flips between consecutive frames and keep rotations
         continuous.
    Return (root_positions, local_rotations).
    """
    raise NotImplementedError


def to_euler_degrees(local_rotations, order: str = "ZXY"):
    """
    TODO: convert to Euler angles in the channel order written to the BVH
    header. scipy.spatial.transform.Rotation does this.
    """
    raise NotImplementedError
