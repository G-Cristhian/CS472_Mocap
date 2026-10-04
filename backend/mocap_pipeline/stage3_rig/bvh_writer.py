"""
Stage 3c: write the .bvh text file.

BVH has two sections:
  HIERARCHY  the skeleton: nested JOINT blocks, each with an OFFSET from its
             parent and its CHANNELS. Root has 6 channels (position +
             rotation), every other joint has 3 (rotation). Leaf joints need
             an "End Site" block.
  MOTION     "Frames: N", "Frame Time: 1/fps", then one line per frame with
             every channel value in hierarchy order.

Check the result by importing it into Blender (File > Import > Motion Capture).
"""
from __future__ import annotations


def write_hierarchy(lines: list[str], rest_offsets) -> None:
    """
    TODO: recurse through joints.RIG_PARENTS from the root, appending
    indented ROOT / JOINT / End Site blocks. Offsets in centimetres.
    """
    raise NotImplementedError


def write_bvh(path: str, rest_offsets, root_positions, euler_degrees, fps: float) -> None:
    """
    TODO:
      1. write_hierarchy.
      2. MOTION header with frame count and frame time.
      3. One line per frame: root X Y Z position, then each joint's three
         Euler angles in the same order the hierarchy declared them.
      4. Write the file as plain ASCII.
    """
    raise NotImplementedError
