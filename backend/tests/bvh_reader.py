"""
A small BVH reader with forward kinematics, so a written .bvh can be checked
against the joint positions it was made from. Independent of bvh_writer.py on
purpose: it follows the BVH convention as Blender and three.js read it
(offsets in the parent's frame, rotation channels composed in the order the
header lists them, each about the joint's own axis).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

CM_PER_M = 100.0


@dataclass
class Node:
    name: str
    offset: np.ndarray
    channels: list[str] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)
    parent: "Node | None" = None


def _rot(axis: str, degrees: np.ndarray) -> np.ndarray:
    """(F, 3, 3) rotation about one axis."""
    a = np.radians(degrees)
    c, s, o, z = np.cos(a), np.sin(a), np.ones_like(a), np.zeros_like(a)
    if axis == "X":
        rows = [[o, z, z], [z, c, -s], [z, s, c]]
    elif axis == "Y":
        rows = [[c, z, s], [z, o, z], [-s, z, c]]
    else:
        rows = [[c, -s, z], [s, c, z], [z, z, o]]
    return np.array(rows).transpose(2, 0, 1)


def read_bvh(path: str):
    """
    Returns (root, frame_time, motion) where motion is (F, n_channels).
    End Sites become nodes named "<parent>_end" with no channels.
    """
    tokens = open(path).read().split()
    i = 0

    def take():
        nonlocal i
        i += 1
        return tokens[i - 1]

    assert take() == "HIERARCHY"
    root = None
    stack: list[Node] = []

    while True:
        tok = take()
        if tok in ("ROOT", "JOINT"):
            node = Node(name=take(), offset=np.zeros(3))
            if stack:
                node.parent = stack[-1]
                stack[-1].children.append(node)
            else:
                root = node
            assert take() == "{"
            stack.append(node)
        elif tok == "End":
            assert take() == "Site"
            node = Node(name=stack[-1].name + "_end", offset=np.zeros(3), parent=stack[-1])
            stack[-1].children.append(node)
            assert take() == "{"
            stack.append(node)
        elif tok == "OFFSET":
            stack[-1].offset = np.array([float(take()) for _ in range(3)])
        elif tok == "CHANNELS":
            n = int(take())
            stack[-1].channels = [take() for _ in range(n)]
        elif tok == "}":
            stack.pop()
        elif tok == "MOTION":
            break

    assert take() == "Frames:"
    n_frames = int(take())
    assert take() == "Frame" and take() == "Time:"
    frame_time = float(take())
    values = np.array([float(v) for v in tokens[i:]], dtype=float)
    motion = values.reshape(n_frames, -1)
    return root, frame_time, motion


def joint_positions(path: str) -> dict[str, np.ndarray]:
    """
    Forward kinematics over every frame: {joint name: (F, 3) positions in
    metres}. End Sites are included as "<parent>_end".
    """
    root, _, motion = read_bvh(path)
    F = len(motion)
    positions: dict[str, np.ndarray] = {}
    col = [0]

    def visit(node: Node, parent_pos, parent_rot):
        pos = parent_pos + np.einsum("fij,j->fi", parent_rot, node.offset)
        rot = parent_rot.copy()
        local = np.tile(np.eye(3), (F, 1, 1))
        for ch in node.channels:
            values = motion[:, col[0]]
            col[0] += 1
            if ch.endswith("position"):
                axis = "XYZ".index(ch[0])
                pos = pos.copy()
                pos[:, axis] += values          # root translation, in the parent's (world) frame
            else:
                local = local @ _rot(ch[0], values)
        rot = parent_rot @ local
        positions[node.name] = pos / CM_PER_M
        for child in node.children:
            visit(child, pos, rot)

    visit(root, np.zeros((F, 3)), np.tile(np.eye(3), (F, 1, 1)))
    return positions
