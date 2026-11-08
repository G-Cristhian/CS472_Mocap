"""
Frame-by-frame numbers for one finished run, for the desktop tester's result
panel: where each camera is, what each camera's detector saw on the shared
clock, where the 3D joints land back in each camera, and how far apart the two
are, in pixels and in millimetres at the performer.

Everything comes from the files a run leaves next to its output, so any past
run can be reported on without detecting again:

    out3d.keypoints.<camera>.npz   2D joints per camera (stage 1)
    out3d.sync.json                clap times and the shared clock (stage 2a)
    calibration.json               the cameras (stage 2b; metres, Y up, floor at 0)
    out3d.pose.npz                 3D joints before smoothing (stage 2c)

    python -m mocap_pipeline.report backend/output/<take>/out3d.json [--calibration FILE]

writes <out>.report.json next to them and prints its path.

The error of one camera for one joint is the distance between where that
camera's detector put the joint and where the triangulated 3D joint projects
into the same image (the reprojection error). It is computed for every camera
that saw the joint with confidence >= config.TRIANGULATION_MIN_CONFIDENCE,
including views the triangulation left out as outliers, so a camera that kept
getting a joint wrong shows it. The joint's own error per frame averages only
the views under config.MAX_REPROJECTION_ERROR_PX, the ones triangulation kept.
Millimetres are pixels times the joint's distance from the camera over the
focal length: how far apart the two would be at the performer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import config, io
from .joints import MEDIAPIPE_JOINTS
from .stage2_reconstruct.sync import _resample

# bump when the layout changes: the desktop tester rebuilds reports of another version
VERSION = 2


def report_path(out_path: str | Path) -> Path:
    return Path(out_path).with_suffix(".report.json")


def calibration_for(out_path: str | Path) -> Path:
    """The calibration this run used: next to the output, or the reused file its metrics name."""
    out = Path(out_path)
    beside = out.parent / "calibration.json"
    if beside.exists():
        return beside
    metrics_path = out.with_suffix(".metrics.json")
    if metrics_path.exists():
        reused = json.loads(metrics_path.read_text()).get("calibrate", {}).get("reused_file")
        if reused and Path(reused).exists():
            return Path(reused)
    raise FileNotFoundError(f"no calibration.json next to {out} and none named in its metrics")


def _list(a: np.ndarray, digits: int):
    """Nested lists with NaN as None, rounded, for JSON."""
    rounded = np.round(a.astype(np.float64), digits)
    return np.where(np.isfinite(rounded), rounded, None).tolist()


def _nanmean(a: np.ndarray, axis):
    with np.errstate(all="ignore"):
        count = np.sum(np.isfinite(a), axis=axis)
        total = np.nansum(a, axis=axis)
        return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def build(out_path: str | Path, calibration_path: str | Path | None = None) -> dict:
    out = Path(out_path)
    paths = io.stage_paths(str(out))
    rig = io.load_rig(str(calibration_path or calibration_for(out)))
    ids = [c.camera_id for c in rig.cameras]
    stem = out.with_suffix("")
    keypoints = [io.load_keypoints(f"{stem}.keypoints.{cid}.npz") for cid in ids]
    sync = io.load_sync(str(paths["sync"]))
    pose = io.load_pose3d(str(paths["pose"]))
    common = sync.common_timestamps

    n_frames = min(len(common), len(pose.points))
    common = common[:n_frames]
    X = pose.points[:n_frames]                                   # (F, J, 3) metres, NaN where not triangulated
    views = pose.num_views[:n_frames]                            # (F, J)

    seen2d, reproj, err_px, err_mm, cameras = [], [], [], [], []
    for cam, kp in zip(rig.cameras, keypoints):
        points, confidence = _resample(kp, kp.timestamps - sync.clap_time_s[cam.camera_id], common)
        used = (confidence >= config.TRIANGULATION_MIN_CONFIDENCE) & np.isfinite(points).all(axis=2)
        p2d = np.where(used[..., None], points, np.nan)

        Xc = X @ cam.R.T + cam.t                                 # camera coordinates, Z forward
        z = Xc[..., 2]
        with np.errstate(all="ignore"):
            uv = (Xc @ cam.K.T)[..., :2] / z[..., None]
        uv[~(z > 0)] = np.nan
        e = np.linalg.norm(p2d - uv, axis=2)                     # NaN unless both exist
        fx = float(cam.K[0, 0])

        seen2d.append(p2d)
        reproj.append(uv)
        err_px.append(e)
        err_mm.append(e * z / fx * 1000.0)

        position = -cam.R.T @ cam.t
        distance = np.nanmedian(np.where(np.isfinite(z), z, np.nan)) if np.isfinite(z).any() else np.nan
        cameras.append({
            "id": cam.camera_id,
            "width": kp.width,
            "height": kp.height,
            "position": _list(position, 4),
            # what the camera looks at, and its image's up, in world axes
            "forward": _list(cam.R.T @ np.array([0.0, 0.0, 1.0]), 4),
            "up": _list(cam.R.T @ np.array([0.0, -1.0, 0.0]), 4),
            "focal_px": round(fx, 2),
            "centre_px": [round(float(cam.K[0, 2]), 2), round(float(cam.K[1, 2]), 2)],
            "calibration_error_px": rig.reprojection_error_px.get(cam.camera_id),
            "distance_m": None if not np.isfinite(distance) else round(float(distance), 3),
            # one pixel in this camera is this many millimetres at the performer
            "mm_per_px": None if not np.isfinite(distance) else round(float(distance / fx * 1000.0), 3),
        })

    err_px = np.stack(err_px)                                    # (C, F, J)
    err_mm = np.stack(err_mm)
    kept = err_px < config.MAX_REPROJECTION_ERROR_PX

    # joints some camera ever reported: MediaPipe gives all 33, RTMPose fewer
    provided = [j for j in range(len(MEDIAPIPE_JOINTS))
                if any(np.isfinite(s[:, j]).any() for s in seen2d)]

    def per_camera(c: int) -> dict:
        e = err_px[c][:, provided]
        m = err_mm[c][:, provided]
        seen = np.isfinite(seen2d[c][:, provided, 0])
        return {
            "id": ids[c],
            "error_px": _list(_nanmean(e, 1), 2),                # per frame, mean over joints
            "error_mm": _list(_nanmean(m, 1), 1),
            "seen": seen.sum(axis=1).tolist(),                   # joints detected confidently per frame
            "mean_error_px": _list(np.array(_nanmean(e.ravel(), 0)), 2),
            "mean_error_mm": _list(np.array(_nanmean(m.ravel(), 0)), 1),
            "lost_fraction": round(float(np.mean(seen.sum(axis=1) == 0)), 4),
            "points": _list(seen2d[c][:, provided], 1),          # (F, J, 2) image pixels or None
            "reprojected": _list(reproj[c][:, provided], 1),
        }

    with np.errstate(all="ignore"):
        centre = np.nanmedian(X.reshape(-1, 3), axis=0) if np.isfinite(X).any() else np.full(3, np.nan)
    joint_px = _nanmean(np.where(kept, err_px, np.nan), 0)[:, provided]   # (F, J)
    joint_mm = _nanmean(np.where(kept, err_mm, np.nan), 0)[:, provided]
    return {
        "version": VERSION,
        "fps": float(config.TARGET_FPS),
        "times": _list(common, 4),
        "joints": [MEDIAPIPE_JOINTS[j] for j in provided],
        "thresholds": {
            "min_confidence": config.TRIANGULATION_MIN_CONFIDENCE,
            "max_reprojection_px": config.MAX_REPROJECTION_ERROR_PX,
        },
        "cameras": cameras,
        # the middle of everything triangulated: where the cameras look from, for their angles
        "performer_centre": _list(centre, 3),
        "per_camera": [per_camera(c) for c in range(len(ids))],
        "joint_views": views[:, provided].tolist(),              # cameras used per joint per frame, 0 = no 3D
        "joint_error_px": _list(joint_px, 2),
        "joint_error_mm": _list(joint_mm, 1),
    }


def write(out_path: str | Path, calibration_path: str | Path | None = None) -> Path:
    data = build(out_path, calibration_path)
    target = report_path(out_path)
    target.write_text(json.dumps(data, separators=(",", ":")))
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", help="the run's output JSON, e.g. backend/output/<take>/out3d.json")
    parser.add_argument("--calibration", help="calibration file (default: next to the output)")
    args = parser.parse_args()
    print(write(args.out, args.calibration))


if __name__ == "__main__":
    main()
