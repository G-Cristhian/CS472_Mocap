"""
Read and write the schemas.py dataclasses as files so each stage can be run
and debugged on its own, and so teammates can hand each other sample data.

Formats:
  * Keypoints2D and Pose3D: one .npz each (numpy arrays, compressed). Scalar
    and string fields are stored as 0-d arrays and read back with .item().
  * SyncResult and CameraRig: JSON, since they are small and people will want
    to read them (was the clap found at a sensible time? where are the cameras?).

run_pipeline.py writes every stage's result next to the output with these
names (see stage_paths) and, with --resume, loads them instead of recomputing.
A keypoints file also records a fingerprint of its source video so a changed
or swapped video is detected and re-detected rather than silently reused.
Keypoints and Pose3D arrays hold every joint in joints.JOINTS order; files
saved before the extra joints existed have MediaPipe's 33 only, and
run_pipeline --resume detects (or triangulates) those again.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .joints import JOINTS
from .schemas import Camera, CameraRig, Keypoints2D, Pose3D, SyncResult


# ---- where each stage's file lives, given the final output path ---------------

def stage_paths(out_path: str, camera_ids: list[str] | None = None) -> dict:
    """
    File per stage next to the output, named after it. For out3d.json:
        keypoints  out3d.keypoints.<camera_id>.npz   (one per camera)
        sync       out3d.sync.json
        pose       out3d.pose.npz                    (triangulated, before smoothing)
        metrics    out3d.metrics.json                (quality numbers, metrics.py)
        log        out3d.log                         (everything printed, time-stamped)
    Calibration has its own path (--calibration), not derived from --out.
    """
    out = Path(out_path)
    stem = out.with_suffix("")
    paths = {
        "sync": Path(f"{stem}.sync.json"),
        "pose": Path(f"{stem}.pose.npz"),
        "metrics": Path(f"{stem}.metrics.json"),
        "log": Path(f"{stem}.log"),
    }
    if camera_ids is not None:
        paths["keypoints"] = {cid: Path(f"{stem}.keypoints.{cid}.npz") for cid in camera_ids}
    return paths


def video_fingerprint(video_path: str) -> dict:
    """Size and modification time of the video; enough to notice a changed or swapped file."""
    st = os.stat(video_path)
    return {"size": int(st.st_size), "mtime_ns": int(st.st_mtime_ns)}


def fingerprint_matches(saved: dict, video_path: str) -> bool:
    try:
        return video_fingerprint(video_path) == {"size": int(saved["size"]), "mtime_ns": int(saved["mtime_ns"])}
    except (OSError, KeyError, TypeError, ValueError):
        return False


# ---- Keypoints2D -------------------------------------------------------------

def save_keypoints(kp: Keypoints2D, path: str, fingerprint: dict | None = None) -> None:
    """
    Every field of Keypoints2D in one compressed .npz. `fingerprint` (from
    video_fingerprint) is stored alongside so load_keypoints callers can check
    the video has not changed; it defaults to the fingerprint of kp.video_path
    when that file exists.
    """
    if fingerprint is None and os.path.exists(kp.video_path):
        fingerprint = video_fingerprint(kp.video_path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        camera_id=np.array(kp.camera_id),
        video_path=np.array(kp.video_path),
        width=np.array(int(kp.width)),
        height=np.array(int(kp.height)),
        fps=np.array(float(kp.fps)),
        timestamps=np.asarray(kp.timestamps, dtype=np.float64),
        points=np.asarray(kp.points, dtype=np.float32),
        confidence=np.asarray(kp.confidence, dtype=np.float32),
        fingerprint=np.array(json.dumps(fingerprint or {})),
    )


def load_keypoints(path: str, with_fingerprint: bool = False):
    """Keypoints2D back from save_keypoints; with_fingerprint=True also returns the stored fingerprint."""
    with np.load(path, allow_pickle=False) as data:
        kp = Keypoints2D(
            camera_id=str(data["camera_id"].item()),
            video_path=str(data["video_path"].item()),
            width=int(data["width"].item()),
            height=int(data["height"].item()),
            fps=float(data["fps"].item()),
            timestamps=data["timestamps"].astype(np.float64),
            points=data["points"].astype(np.float64),
            confidence=data["confidence"].astype(np.float64),
        )
        fingerprint = json.loads(str(data["fingerprint"].item())) if "fingerprint" in data else {}
    return (kp, fingerprint) if with_fingerprint else kp


# ---- SyncResult ----------------------------------------------------------------

def save_sync(sync: SyncResult, path: str) -> None:
    """JSON: the clap time per camera and the shared timeline."""
    data = {
        "clap_time_s": {cid: float(t) for cid, t in sync.clap_time_s.items()},
        "common_timestamps": np.asarray(sync.common_timestamps, dtype=np.float64).tolist(),
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fp:
        json.dump(data, fp, indent=2)


def load_sync(path: str) -> SyncResult:
    with open(path) as fp:
        data = json.load(fp)
    return SyncResult(
        clap_time_s={str(cid): float(t) for cid, t in data["clap_time_s"].items()},
        common_timestamps=np.asarray(data["common_timestamps"], dtype=np.float64),
    )


# ---- CameraRig ---------------------------------------------------------------

def save_rig(rig: CameraRig, path: str) -> None:
    """JSON; K, R, t as nested lists. Reused by run_pipeline.py on the next run."""
    data = {
        "is_metric": rig.is_metric,
        "reprojection_error_px": rig.reprojection_error_px,
        "cameras": [{"camera_id": c.camera_id, "K": np.asarray(c.K).tolist(),
                     "R": np.asarray(c.R).tolist(), "t": np.asarray(c.t).tolist()} for c in rig.cameras],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fp:
        json.dump(data, fp, indent=2)


def load_rig(path: str) -> CameraRig:
    with open(path) as fp:
        data = json.load(fp)

    cameras = [Camera(camera_id=c["camera_id"], K=np.array(c["K"]), R=np.array(c["R"]), t=np.array(c["t"]))
               for c in data["cameras"]]

    return CameraRig(cameras=cameras, reprojection_error_px=data.get("reprojection_error_px", {}),
                     is_metric=data.get("is_metric", False))


# ---- Pose3D ------------------------------------------------------------------

def save_pose3d(pose: Pose3D, path: str) -> None:
    """Compressed .npz with the 3D joints, the per-joint camera count and fps."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        fps=np.array(float(pose.fps)),
        points=np.asarray(pose.points, dtype=np.float32),
        num_views=np.asarray(pose.num_views, dtype=np.int16),
    )


def load_pose3d(path: str) -> Pose3D:
    with np.load(path, allow_pickle=False) as data:
        return Pose3D(
            fps=float(data["fps"].item()),
            points=data["points"].astype(np.float64),
            num_views=data["num_views"].astype(np.int64),
        )


def save_pose3d_json(pose: Pose3D, path: str, timestamps=None) -> None:
    """
    The 3D joints as JSON for the frontend:
    [{"t": seconds, "landmarks": {"NOSE": {"x":..,"y":..,"z":..} or null, ...}}, ...]
    Every joint in joints.JOINTS, by name. Metres, Y up, floor at Y = 0 (see
    stage2_reconstruct/scale_floor.py). t is seconds from the clap. null means
    fewer than 2 cameras saw the joint, or the detector does not have it
    (MediaPipe has none of joints.EXTRA_JOINTS).
    """
    frames = []
    for f, frame in enumerate(pose.points):
        landmarks = {}

        for name, p in zip(JOINTS, frame):
            landmarks[name] = None if np.isnan(p).any() else {
                "x": round(float(p[0]), 4), "y": round(float(p[1]), 4), "z": round(float(p[2]), 4)}

        t = timestamps[f] if timestamps is not None else f / pose.fps
        frames.append({"t": round(float(t), 4), "landmarks": landmarks})

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fp:
        json.dump(frames, fp)
