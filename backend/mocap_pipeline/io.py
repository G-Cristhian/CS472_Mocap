"""
Read and write the schemas.py dataclasses as files so each stage can be run
and debugged on its own, and so teammates can hand each other sample data.

Suggested format: one .npz per object (numpy arrays) with scalar and string
fields stored alongside. JSON is fine for CameraRig since it is small and
people will want to read it.
"""
import json
import numpy as np

from __future__ import annotations
from .joints import MEDIAPIPE_JOINTS
from .schemas import Camera, CameraRig, Keypoints2D, Pose3D, SyncResult


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
    """JSON; K, R, t as nested lists. Reused by run_pipeline.py on the next run."""
    data = {
        "is_metric": rig.is_metric,
        "reprojection_error_px": rig.reprojection_error_px,
        "cameras": [{"camera_id": c.camera_id, "K": np.asarray(c.K).tolist(),
                     "R": np.asarray(c.R).tolist(), "t": np.asarray(c.t).tolist()} for c in rig.cameras],
    }

    with open(path, "w") as fp:
        json.dump(data, fp, indent=2)


def load_rig(path: str) -> CameraRig:
    with open(path) as fp:
        data = json.load(fp)

    cameras = [Camera(camera_id=c["camera_id"], K=np.array(c["K"]), R=np.array(c["R"]), t=np.array(c["t"]))
               for c in data["cameras"]]
    
    return CameraRig(cameras=cameras, reprojection_error_px=data.get("reprojection_error_px", {}),
                     is_metric=data.get("is_metric", False))


def save_pose3d(pose: Pose3D, path: str) -> None:
    raise NotImplementedError


def load_pose3d(path: str) -> Pose3D:
    raise NotImplementedError


def save_pose3d_json(pose: Pose3D, path: str, timestamps=None) -> None:
    """
    The 3D joints as JSON for the frontend:
    [{"t": seconds, "landmarks": {"NOSE": {"x":..,"y":..,"z":..} or null, ...}}, ...]
    Metres, Y up, floor at Y = 0 (see stage2_reconstruct/scale_floor.py). t is
    seconds from the clap. null means fewer than 2 cameras saw the joint.
    """
    frames = []
    for f, frame in enumerate(pose.points):
        landmarks = {}

        for name, p in zip(MEDIAPIPE_JOINTS, frame):
            landmarks[name] = None if np.isnan(p).any() else {
                "x": round(float(p[0]), 4), "y": round(float(p[1]), 4), "z": round(float(p[2]), 4)}
            
        t = timestamps[f] if timestamps is not None else f / pose.fps
        frames.append({"t": round(float(t), 4), "landmarks": landmarks})

    with open(path, "w") as fp:
        json.dump(frames, fp)
