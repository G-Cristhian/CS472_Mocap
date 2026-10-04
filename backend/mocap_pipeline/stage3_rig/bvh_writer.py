# Based on video2bvh (github.com/KevinLTT/video2bvh), bvh_skeleton/bvh_helper.py (write_header, write_bvh):
# the recursive ROOT / JOINT / End Site writer and the MOTION section. Changed for our data: works from
# joints.RIG_PARENTS and our offsets dict instead of BvhNode objects, metres converted to centimetres, and the
# frame time from the take's fps.
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
Stage 3c: write the .bvh text file.

BVH has two sections:
  HIERARCHY  the skeleton: nested JOINT blocks, each with an OFFSET from its
             parent and its CHANNELS. Root has 6 channels (position +
             rotation), every other joint has 3 (rotation). Leaf joints need
             an "End Site" block.
  MOTION     "Frames: N", "Frame Time: 1/fps", then one line per frame with
             every channel value in hierarchy order.

Units are centimetres, Y up (the usual BVH convention; three.js BVHLoader and
Blender read it as is). Rotation channels are Zrotation Xrotation Yrotation.

Check the result by importing it into Blender (File > Import > Motion Capture).
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

from ..joints import RIG_END_SITES, RIG_JOINTS, RIG_PARENTS

CM_PER_M = 100.0
ROTATION_ORDER = "ZXY"


def _children(name):
    return [j for j in RIG_JOINTS if RIG_PARENTS[j] == name]


def channel_order():
    """Rotating joints in the order the hierarchy writes them (depth first)."""
    order = []

    def visit(name):
        if name in RIG_END_SITES:
            return
        order.append(name)
        for child in _children(name):
            visit(child)

    visit(RIG_JOINTS[0])

    return order


def write_hierarchy(lines: list[str], rest_offsets) -> None:
    """
    Recurse through joints.RIG_PARENTS from the root, appending indented
    ROOT / JOINT / End Site blocks. Offsets in centimetres.
    """
    def offset(name):
        x, y, z = (CM_PER_M * float(v) for v in rest_offsets[name])

        return f"OFFSET {x:.6f} {y:.6f} {z:.6f}"

    rotation_channels = " ".join(f"{axis}rotation" for axis in ROTATION_ORDER)

    def visit(name, level):
        indent = " " * 4 * level
        inner = " " * 4 * (level + 1)

        if name in RIG_END_SITES:
            lines.extend([f"{indent}End Site", f"{indent}{{", f"{inner}{offset(name)}", f"{indent}}}"])
            return
        if RIG_PARENTS[name] is None:
            lines.extend([f"{indent}ROOT {name}", f"{indent}{{", f"{inner}{offset(name)}",
                         f"{inner}CHANNELS 6 Xposition Yposition Zposition {rotation_channels}"])
        else:
            lines.extend([f"{indent}JOINT {name}", f"{indent}{{", f"{inner}{offset(name)}",
                         f"{inner}CHANNELS 3 {rotation_channels}"])
            
        children = _children(name)

        for child in children:
            visit(child, level + 1)

        if not children:
            end = name + "EndSite"
            end_offset = offset(end) if end in rest_offsets else "OFFSET 0.000000 0.000000 0.000000"
            lines.extend([f"{inner}End Site", f"{inner}{{", f"{inner}    {end_offset}", f"{inner}}}"])
            
        lines.append(f"{indent}}}")

    visit(RIG_JOINTS[0], 0)


def write_bvh(path: str, rest_offsets, root_positions, euler_degrees, fps: float) -> None:
    """
      1. write_hierarchy.
      2. MOTION header with frame count and frame time.
      3. One line per frame: root X Y Z position (cm), then each joint's three
         Euler angles in the same order the hierarchy declared them.
         euler_degrees is (F, J, 3) for the rotating joints in RIG_JOINTS order
         (rotations.solve_rotations / to_euler_degrees).
      4. Write the file as plain ASCII.
    """
    rotating = [n for n in RIG_JOINTS if n not in RIG_END_SITES]
    order = [rotating.index(n) for n in channel_order()]

    lines = ["HIERARCHY"]
    write_hierarchy(lines, rest_offsets)
    lines.extend(["MOTION", f"Frames: {len(root_positions)}", f"Frame Time: {1.0 / fps:.8f}"])

    root_cm = np.asarray(root_positions) * CM_PER_M
    angles = np.asarray(euler_degrees)[:, order].reshape(len(root_positions), -1)
    for pos, rot in zip(root_cm, angles):
        lines.append(" ".join(f"{v:.6f}" for v in np.r_[pos, rot]))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
