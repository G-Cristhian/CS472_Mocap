# Based on video2bvh (github.com/KevinLTT/video2bvh), bvh_skeleton/h36m_skeleton.py (pose2euler: each joint's
# orientation built from two directions in the pose, local = parent^-1 x global, Euler angles in ZXY order) and
# bvh_skeleton/math3d.py (dcm_from_axis). Changed for our data: Y-up instead of Z-up, the rotation maths done with
# scipy's standard rotations instead of math3d's left-handed quaternions, and vectorised over all frames.
#
# video2bvh is MIT licensed:
#   Copyright (c) 2020 KevinLTT
#   Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#   documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#   the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
#   to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#   The above copyright notice and this permission notice shall be included in all copies or substantial portions
#   of the Software.
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
#   THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
#   CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#   DEALINGS IN THE SOFTWARE.
"""
Stage 3b: positions -> joint rotations.

Rig files store, per frame, how each joint is ROTATED relative to its parent
plus the root's position. This is the hardest part of stage 3.

Input : rig joint positions (F, R, 3) and the rest pose offsets.
Output: root position (F, 3) and local rotations per joint per frame.

How (video2bvh's approach): every joint's orientation is built from two
directions measured in the pose, e.g. the hips from the hip line (left/right)
and the spine (up). The T-pose has every joint frame equal to the identity,
so that measured frame IS the joint's world rotation. Joints whose only child
is an End Site (ankles, wrists) copy their parent's rotation.

Known limitation: twist along a limb can't be recovered from joint positions,
so arm twist follows the body's up direction and leg twist the hip line.
"""
from __future__ import annotations

import numpy as np

from ..joints import RIG_END_SITES, RIG_JOINTS, RIG_PARENTS

AXES = {"x": 0, "y": 1, "z": 2}

# joint -> (primary axis, its direction), (secondary axis, its direction)
# a direction is (to, from): the vector from joint `from` to joint `to`
# (video2bvh's choices, in Y-up: +X performer's left, +Y up)
FRAME_RULES = {
    "Hip":           (("x", ("LeftHip", "RightHip")), ("y", ("Spine", "Hip"))),
    "RightHip":      (("y", ("RightHip", "RightKnee")), ("x", ("Hip", "RightHip"))),
    "RightKnee":     (("y", ("RightKnee", "RightAnkle")), ("x", ("Hip", "RightHip"))),
    "LeftHip":       (("y", ("LeftHip", "LeftKnee")), ("x", ("LeftHip", "Hip"))),
    "LeftKnee":      (("y", ("LeftKnee", "LeftAnkle")), ("x", ("LeftHip", "Hip"))),
    "Spine":         (("y", ("Thorax", "Spine")), ("x", ("LeftHip", "RightHip"))),
    "Thorax":        (("x", ("LeftShoulder", "RightShoulder")), ("y", ("Neck", "Thorax"))),
    "Neck":          (("y", ("Head", "Neck")), ("x", ("LeftShoulder", "RightShoulder"))),
    "LeftShoulder":  (("x", ("LeftElbow", "LeftShoulder")), ("y", ("Neck", "Thorax"))),
    "LeftElbow":     (("x", ("LeftWrist", "LeftElbow")), ("y", ("Neck", "Thorax"))),
    "RightShoulder": (("x", ("RightShoulder", "RightElbow")), ("y", ("Neck", "Thorax"))),
    "RightElbow":    (("x", ("RightElbow", "RightWrist")), ("y", ("Neck", "Thorax"))),
}


def _normalize(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)

def _frame_from_axes(primary_axis, primary, secondary_axis, secondary, fallback):
    """
    Rotation matrices (F, 3, 3) whose columns are the joint's x, y, z axes:
    the primary axis points exactly along `primary`, the secondary axis as
    close to `secondary` as possible (video2bvh's dcm_from_axis). Where the
    two are nearly parallel (e.g. an arm raised straight up), `fallback` is
    used as the secondary direction instead.
    """
    a = _normalize(primary)
    s = _normalize(secondary)
    parallel = np.linalg.norm(np.cross(a, s), axis=-1) < 0.2
    s = np.where(parallel[:, None], _normalize(fallback), s)

    i, j = AXES[primary_axis], AXES[secondary_axis]
    k = 3 - i - j

    # third axis from the right-hand rule, then make the secondary exactly perpendicular
    sign = 1.0 if (j - i) % 3 == 1 else -1.0      # x->y, y->z, z->x are the positive order

    c = _normalize(sign * np.cross(a, s))
    b = _normalize(sign * np.cross(c, a))
    R = np.empty(a.shape[:-1] + (3, 3))
    R[..., :, i], R[..., :, j], R[..., :, k] = a, b, c

    return R


def bone_rotation(rest_direction, current_direction):
    """
    Smallest rotation (3x3) taking one unit vector onto another: axis = cross
    product, angle = arccos of the dot product; handles the parallel and
    opposite cases.
    """
    a = _normalize(np.asarray(rest_direction, dtype=float))
    b = _normalize(np.asarray(current_direction, dtype=float))
    axis = np.cross(a, b)
    s, c = np.linalg.norm(axis), float(np.dot(a, b))

    if s < 1e-9:
        if c > 0:
            return np.eye(3)
        
        # opposite: half a turn about any axis perpendicular to a
        perp = np.cross(a, [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 1.0, 0.0])
        perp = _normalize(perp)

        return 2 * np.outer(perp, perp) - np.eye(3)
    
    k = axis / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * K @ K


def solve_rotations(rig_positions, rest_offsets):
    """
      1. Root (Hip): orientation from the hip line and the spine; root
         position = Hip position.
      2. Every other joint: orientation from FRAME_RULES; ankles and wrists
         copy their parent's.
      3. Local rotation = inverse(parent world rotation) x world rotation.
    Returns (root_positions (F, 3), local_rotations (F, J, 3, 3)) with J the
    rotating joints (RIG_JOINTS minus RIG_END_SITES) in RIG_JOINTS order.
    rest_offsets is not needed here: the T-pose frames are all the identity.
    """
    index = {name: i for i, name in enumerate(RIG_JOINTS)}

    def vec(pair):
        to, frm = pair
        return rig_positions[:, index[to]] - rig_positions[:, index[frm]]

    body_up = vec(("Neck", "Thorax"))
    body_left = vec(("LeftShoulder", "RightShoulder"))
    body_forward = np.cross(body_left, body_up)

    world = {}

    for name in RIG_JOINTS:
        if name in RIG_END_SITES:
            continue
        if name in FRAME_RULES:
            (pa, pv), (sa, sv) = FRAME_RULES[name]
            # fallback secondary for the rare frames where the two directions line up
            fallback = body_forward if sa == "y" else body_up
            world[name] = _frame_from_axes(pa, vec(pv), sa, vec(sv), fallback)
        else:
            world[name] = world[RIG_PARENTS[name]]

    rotating = [n for n in RIG_JOINTS if n not in RIG_END_SITES]
    local = np.empty((len(rig_positions), len(rotating), 3, 3))

    for r, name in enumerate(rotating):
        parent = RIG_PARENTS[name]
        local[:, r] = world[name] if parent is None else \
            np.transpose(world[parent], (0, 2, 1)) @ world[name]

    return rig_positions[:, index["Hip"]].copy(), local


def to_euler_degrees(local_rotations, order: str = "ZXY"):
    """
    Euler angles in the channel order written to the BVH header, using
    scipy.spatial.transform.Rotation (upper case = intrinsic, which is how
    BVH channels compose: R = Rz Rx Ry for ZXY). Angles are unwrapped over
    time so they don't jump by 360 degrees between frames.
    Returns (F, J, 3), angles in `order`.
    """
    from scipy.spatial.transform import Rotation

    F, J = local_rotations.shape[:2]
    euler = Rotation.from_matrix(local_rotations.reshape(-1, 3, 3)).as_euler(order.upper(), degrees=True)
    euler = euler.reshape(F, J, 3)
    
    return np.unwrap(euler, period=360.0, axis=0)
