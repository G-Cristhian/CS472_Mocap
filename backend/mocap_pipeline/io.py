"""
Read and write the schemas.py dataclasses as files so each stage can be run
and debugged on its own, and so teammates can hand each other sample data.

Suggested format: one .npz per object (numpy arrays) with scalar and string
fields stored alongside. JSON is fine for CameraRig since it is small and
people will want to read it.
"""
from __future__ import annotations

from .schemas import CameraRig, Keypoints2D, Pose3D, SyncResult


def save_keypoints(kp: Keypoints2D, path: str) -> None:
    # TODO: np.savez_compressed with every field of Keypoints2D.
    raise NotImplementedError


def load_keypoints(path: str) -> Keypoints2D:
    raise NotImplementedError


def save_sync(sync: SyncResult, path: str) -> None:
    raise NotImplementedError


def load_sync(path: str) -> SyncResult:
    raise NotImplementedError


def save_rig(rig: CameraRig, path: str) -> None:
    # TODO: JSON; convert K, R, t to nested lists.
    raise NotImplementedError


def load_rig(path: str) -> CameraRig:
    raise NotImplementedError


def save_pose3d(pose: Pose3D, path: str) -> None:
    raise NotImplementedError


def load_pose3d(path: str) -> Pose3D:
    raise NotImplementedError
