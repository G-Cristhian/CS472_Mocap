# Based on video2bvh (github.com/KevinLTT/video2bvh), bvh_skeleton/h36m_skeleton.py: the H36M skeleton's T-pose
# directions, bone lengths averaged over left and right, and End Sites 0.4 x their parent bone. Changed for our
# data: Y-up instead of Z-up, median instead of mean, MediaPipe joints mapped to H36M (joints.RIG_JOINT_SOURCES).
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
Stage 3a: turn the loose joints (joints.JOINTS) into a skeleton with fixed bone lengths.

Input : cleaned Pose3D (metres, Y up).
Output: rig joint positions per frame + one constant length per bone.

The rig is the 17-joint H36M skeleton (joints.RIG_JOINTS). Axes: +Y up,
+X the performer's left, +Z the way they face in the T-pose.
"""
from __future__ import annotations

import numpy as np

from .. import config, metrics
from ..joints import JOINT_INDEX, RIG_END_SITES, RIG_JOINT_DETECTED, RIG_JOINT_SOURCES, RIG_JOINTS, RIG_PARENTS
from ..schemas import Pose3D

# T-pose direction of each bone, from its parent joint to the joint (video2bvh's
# initial_directions, turned from Z-up to Y-up)
REST_DIRECTIONS = {
    "Hip":           (0, 0, 0),
    "RightHip":      (-1, 0, 0),
    "RightKnee":     (0, -1, 0),
    "RightAnkle":    (0, -1, 0),
    "LeftHip":       (1, 0, 0),
    "LeftKnee":      (0, -1, 0),
    "LeftAnkle":     (0, -1, 0),
    "Spine":         (0, 1, 0),
    "Thorax":        (0, 1, 0),
    "Neck":          (0, 1, 0),
    "Head":          (0, 1, 0),
    "LeftShoulder":  (1, 0, 0),
    "LeftElbow":     (1, 0, 0),
    "LeftWrist":     (1, 0, 0),
    "RightShoulder": (-1, 0, 0),
    "RightElbow":    (-1, 0, 0),
    "RightWrist":    (-1, 0, 0),
}
# End Sites added after the leaf joints: (direction, fraction of the joint's own bone length)
END_SITE_DIRECTIONS = {
    "RightAnkle": ((0, 0, 1), 0.4),     # foot, pointing forward
    "LeftAnkle":  ((0, 0, 1), 0.4),
    "LeftWrist":  ((1, 0, 0), 0.4),     # hand, along the forearm
    "RightWrist": ((-1, 0, 0), 0.4),
}


def _fill_missing(positions):
    """
    Frames where a joint is missing are filled from its neighbours (straight
    line between the nearest frames that have it), or copied from the
    nearest frame at the start and end of the take.
    """
    out = positions.copy()
    frames = np.arange(len(positions))

    for j in range(positions.shape[1]):
        known = np.isfinite(positions[:, j]).all(axis=1)
        if not known.any():
            raise ValueError(f"{RIG_JOINTS[j]} is never seen in this take, can't build a skeleton")
        if known.all():
            continue
        for axis in range(3):
            out[:, j, axis] = np.interp(frames, frames[known], positions[known, j, axis])

    return out


def rig_joint_positions(pose: Pose3D):
    """
    For each entry of joints.RIG_JOINT_SOURCES, average (or weight) the listed
    MediaPipe joints. A rig joint in joints.RIG_JOINT_DETECTED takes the
    detected joint instead in the frames that have it (unless
    config.RIG_USES_DETECTED_JOINTS is off). Missing frames are filled from
    neighbouring frames, so the result has no NaN. Returns
    (F, len(RIG_JOINTS), 3) in RIG_JOINTS order.
    """
    points = pose.points
    rig = np.empty((len(points), len(RIG_JOINTS), 3))

    for r, name in enumerate(RIG_JOINTS):
        source = RIG_JOINT_SOURCES[name]
        weights = source if isinstance(source, dict) else {s: 1.0 / len(source) for s in source}
        rig[:, r] = sum(w * points[:, JOINT_INDEX[s]] for s, w in weights.items())

        if name in RIG_JOINT_DETECTED and config.RIG_USES_DETECTED_JOINTS:
            detected = points[:, JOINT_INDEX[RIG_JOINT_DETECTED[name]]]
            found = np.isfinite(detected).all(axis=1)
            rig[found, r] = detected[found]
            metrics.record(f"rig.detected_fraction.{name}", float(found.mean()) if len(found) else 0.0)

    return _fill_missing(rig)


def bone_lengths(rig_positions):
    """
    For each joint with a parent (joints.RIG_PARENTS), the MEDIAN over all
    frames of its distance to the parent. Left and right versions of a bone
    are averaged so the skeleton is symmetric. Returns {joint_name: length_m}.
    """
    index = {name: i for i, name in enumerate(RIG_JOINTS)}
    raw = {}

    for name, parent in RIG_PARENTS.items():
        if parent is None:
            continue
        d = np.linalg.norm(rig_positions[:, index[name]] - rig_positions[:, index[parent]], axis=1)
        raw[name] = float(np.median(d))

    lengths = {}

    for name, length in raw.items():
        for side, other in (("Left", "Right"), ("Right", "Left")):
            if name.startswith(side):
                length = (length + raw[other + name[len(side):]]) / 2

        lengths[name] = length

    return lengths


def rest_pose_offsets(lengths):
    """
    The T-pose the rig file declares: each joint's offset from its parent
    (spine and head up +Y, arms out along +X / -X, legs down -Y), in metres.
    End Sites after the ankles and wrists are included as "<joint>EndSite".
    Returns {joint_name: (x, y, z)}. BVH wants centimetres by convention;
    bvh_writer converts.
    """
    offsets = {}

    for name in RIG_JOINTS:
        direction = np.array(REST_DIRECTIONS[name], dtype=float)
        offsets[name] = tuple(direction * lengths.get(name, 0.0))

    for name, (direction, fraction) in END_SITE_DIRECTIONS.items():
        if name not in RIG_END_SITES:
            offsets[name + "EndSite"] = tuple(np.array(direction, dtype=float) * fraction * lengths[name])
            
    return offsets
