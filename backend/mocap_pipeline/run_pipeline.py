"""
Command line entry point: runs every stage in order.

    cd backend
    python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV cam2.mp4 --height-m 1.75 --out take01.json

Every stage writes its result next to --out (io.stage_paths). Re-running with
--resume loads those files instead of recomputing, so a failed or tweaked run
starts from the last good stage instead of running the pose model again.
--detector picks the pose model for stage 1 (stage1_keypoints/backends.py).
--smoother picks the stage 2c smoother (stage2_reconstruct/smooth.py).
--stop-after writes one stage's file and exits, to hand data to a teammate.

This file is the one place that knows the order of the stages. When the web
backend is built later, it should call run() rather than repeat this logic.
"""
from __future__ import annotations
import argparse
import os
import numpy as np

from pathlib import Path
from . import config, io, metrics
from .stage1_keypoints import detect
from .stage1_keypoints.backends import BACKENDS, DEFAULT_BACKEND
from .stage2_reconstruct import calibrate, scale_floor, smooth, sync, triangulate
from .stage3_rig import bvh_writer, rotations, skeleton
from .joints import RIG_JOINTS, RIG_PARENTS
from .stage2_reconstruct.iphone_camera import (is_iphone_video, iphone_intrinsics, IPhoneMetadataError,
                                               MODEL_KEY)

BACKEND_DIR = Path(__file__).resolve().parent.parent
# where results go unless --out / --calibration say otherwise (created when needed)
OUTPUT_DIR = BACKEND_DIR / "output"
DEFAULT_OUT = OUTPUT_DIR / "out3d.json"
DEFAULT_CALIBRATION = OUTPUT_DIR / "calibration.json"

# --stop-after choices, in pipeline order
STAGES = ("keypoints", "sync", "calibrate", "triangulate")


def default_model_path() -> str:
    """MODEL_FILEPATH from .env if set, otherwise config.POSE_MODEL_PATH (relative to backend/)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    env = os.path.expanduser(os.getenv("MODEL_FILEPATH", ""))

    return env or str(BACKEND_DIR / config.POSE_MODEL_PATH)


def camera_types(video_paths, choices):
    """iPhone or webcam per video: auto-detected from the video metadata unless stated."""

    return [("iphone" if is_iphone_video(v) else "webcam") if c == "auto" else c
            for v, c in zip(video_paths, choices)]


def camera_intrinsics(keypoints, video_paths, types, fovs):
    """K per camera: iPhones from their metadata, other cameras from their field of view."""
    intrinsics = []
    for kp, video, kind, fov in zip(keypoints, video_paths, types, fovs):
        size = (kp.width, kp.height)
        if kind == "iphone":
            try:
                K, metadata = iphone_intrinsics(video, size)
                print(f"{video}: {metadata.get(MODEL_KEY, 'iPhone')}, focal length {K[0, 0]:.0f} px from metadata")
                intrinsics.append(K)
                continue
            except IPhoneMetadataError as e:
                print(f"{e}\nFalling back to --fov {fov} for this camera")

        intrinsics.append(calibrate.initial_intrinsics(kp.width, kp.height, fov))

    return intrinsics


def calibrate_cameras(keypoints, video_paths, types, fovs, max_error_px, charuco_videos):
    """
    Our calibration from the performer; if it fails or its error is above
    max_error_px, the ChArUco board (needs one board video per camera).
    Returns (rig, from_board).
    """
    ids = [kp.camera_id for kp in keypoints]
    try:
        rig = calibrate.calibrate_rig(keypoints, camera_intrinsics(keypoints, video_paths, types, fovs))
        error = float(np.mean(list(rig.reprojection_error_px.values())))
        print("Calibration from the performer: " + ", ".join(
            f"{cid} {e:.2f} px" for cid, e in rig.reprojection_error_px.items()))
        
        if error <= max_error_px:
            return rig, False
        
        reason = f"error {error:.2f} px is above --max-error {max_error_px}"
    except calibrate.CalibrationError as e:
        reason = str(e)

    # fallback: only load the board code when the performer calibration was not good enough
    if not charuco_videos:
        boards = " ".join(f"cam{c}_board.mp4" for c in range(len(video_paths)))
        raise SystemExit(f"Calibration from the performer failed ({reason}).\n"
                         f"Record the ChArUco board with every camera and rerun with --charuco-videos {boards}")
    
    print(f"Calibration from the performer failed ({reason}), falling back to the ChArUco board")

    from .stage2_reconstruct.board_calibration import calibrate_from_board

    cgroup, info = calibrate_from_board(charuco_videos)
    calibrate._move_origin_to(cgroup, 0)
    print(f"ChArUco calibration: {info['reprojection_error_px']:.2f} px error")

    return calibrate.group_to_rig(cgroup, ids, {"board": info["reprojection_error_px"]}), True


def camera_ids_for(video_paths: list[str]) -> list[str]:
    """
    Stable camera id per video: the file stem, prefixed with camN_ when two
    videos share a stem (two phones can both save IMG_0001.MOV). Decided before
    detection so --resume can find a camera's keypoints file without running it.
    """
    stems = [Path(v).stem for v in video_paths]
    if len(set(stems)) < len(stems):
        return [f"cam{c}_{s}" for c, s in enumerate(stems)]
    return stems


def _mtime(path) -> float:
    return Path(path).stat().st_mtime


def _up_to_date(path, *inputs) -> bool:
    """True if `path` exists and is at least as new as every existing file in `inputs`."""
    p = Path(path)
    if not p.exists():
        return False
    t = _mtime(p)
    return all(t >= _mtime(i) for i in inputs if Path(i).exists())


def _stop(stage: str, stop_after: str | None) -> bool:
    if stop_after == stage:
        print(f"Stopped after {stage} (--stop-after)")
        return True
    return False


def run(video_paths: list[str], out_path: str, performer_height_m: float | None = None,
        model_path: str | None = None, camera: list[str] | None = None, fov: list[float] | None = None,
        clap_times: list[float] | None = None, calibration_path: str = str(DEFAULT_CALIBRATION),
        recalibrate: bool = False, max_error_px: float = config.CALIB_MAX_ERROR_PX,
        charuco_videos: list[str] | None = None, smoothing: bool = True, bvh: bool = True,
        resume: bool = False, stop_after: str | None = None, detector: str = DEFAULT_BACKEND,
        smoother: str = config.SMOOTHER, clap_threshold: float = 1.0) -> None:
    """
    Runs every stage in order. With resume=True a stage whose file (io.stage_paths)
    exists and is still valid is loaded instead of recomputed. stop_after names
    the last stage to run (one of STAGES); its file is written and run() returns.
    clap_threshold multiplies the clap loudness thresholds in config (0.5
    accepts a clap half as strong, for a noisy room); the clap search is
    skipped when clap_times are given. detector is the stage 1 pose model (a
    name in backends.BACKENDS); saved joints are only reused if the same
    detector made them. smoother is the
    stage 2c filter (a name in smooth.SMOOTHERS); it always runs, so two runs
    with --resume compare smoothers on the same triangulation.

    Every run writes <out>.metrics.json and <out>.log next to the output
    (metrics.py), also when it fails or stops early.
    """
    n = len(video_paths)

    if n < config.MIN_CAMERAS:
        raise ValueError(f"Give at least {config.MIN_CAMERAS} videos, one per camera (got {n}).")
    if stop_after is not None and stop_after not in STAGES:
        raise ValueError(f"stop_after must be one of {STAGES}, got {stop_after!r}")
    if detector not in BACKENDS:
        raise ValueError(f"detector must be one of {tuple(BACKENDS)}, got {detector!r}")
    if smoother not in smooth.SMOOTHERS:
        raise ValueError(f"smoother must be one of {smooth.SMOOTHERS}, got {smoother!r}")
    if not clap_threshold > 0:
        raise ValueError(f"clap_threshold must be positive, got {clap_threshold}")

    metrics.start(out_path, videos=[str(v) for v in video_paths], detector=detector, smoother=smoother,
                  performer_height_m=performer_height_m, resume=resume, stop_after=stop_after)
    try:
        with metrics.time("total"):
            stopped = _run_stages(video_paths, out_path, performer_height_m, model_path, camera, fov, clap_times,
                                  calibration_path, recalibrate, max_error_px, charuco_videos, smoothing, bvh,
                                  resume, stop_after, detector, smoother, clap_threshold)
    except BaseException as e:
        path = metrics.finish("failed", f"{type(e).__name__}: {e}")
        raise
    path = metrics.finish("done" if stopped is None else f"stopped after {stopped}")
    if path is not None and stopped is None:
        print(f"Saved metrics to {path}")


def _run_stages(video_paths, out_path, performer_height_m, model_path, camera, fov, clap_times,
                calibration_path, recalibrate, max_error_px, charuco_videos, smoothing, bvh,
                resume, stop_after, detector, smoother, clap_threshold) -> str | None:
    """The stages in order; returns the stage name if stop_after ended the run early."""
    n = len(video_paths)
    model_path = model_path or default_model_path()
    camera = camera or ["auto"] * n
    fov = fov or [config.DEFAULT_HFOV_DEG] * n

    ids = camera_ids_for(video_paths)
    paths = io.stage_paths(out_path, ids)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    types = camera_types(video_paths, camera)
    print("Cameras: " + ", ".join(f"cam{c} {kind}" for c, kind in enumerate(types)))

    # Stage 1: 2D joints per camera. Saved raw (before sync resamples them).
    keypoints = []
    for video, cid in zip(video_paths, ids):
        kp_path = paths["keypoints"][cid]
        kp = None
        if resume and kp_path.exists():
            saved, fingerprint = io.load_keypoints(str(kp_path), with_fingerprint=True)
            # files saved before --detector existed were all made by MediaPipe
            saved_detector = fingerprint.get("detector", "mediapipe")
            if not io.fingerprint_matches(fingerprint, video):
                print(f"{kp_path.name} was made from a different version of {video}, detecting again")
            elif saved_detector != detector:
                print(f"{kp_path.name} was made with {saved_detector}, detecting again with {detector}")
            else:
                print(f"Using saved joints for {video} ({kp_path.name})")
                kp = saved
        if kp is None:
            print(f"Detecting joints in {video} ({detector})")
            with metrics.time(f"detect.{cid}"):
                kp = detect.detect_video(video, model_path, detector=detector)
            kp.camera_id = cid
            io.save_keypoints(kp, str(kp_path), {**io.video_fingerprint(video), "detector": detector})
        kp.camera_id = cid
        keypoints.append(kp)
        metrics.record(f"stage1.{cid}", metrics.keypoints_summary(kp))

    if _stop("keypoints", stop_after):
        return "keypoints"

    # Stage 2a: one shared clock. A saved sync file supplies the clap times
    # (skipping the audio search); resampling is cheap and always runs.
    sync_path = paths["sync"]
    sync_from_file = False
    if clap_times is None and resume and sync_path.exists():
        saved_sync = io.load_sync(str(sync_path))
        try:
            clap_times = [saved_sync.clap_time_s[cid] for cid in ids]
            sync_from_file = True
            print(f"Using saved clap times from {sync_path.name}")
        except KeyError:
            print(f"{sync_path.name} is for different cameras, searching for the clap again")
    try:
        with metrics.time("sync"):
            sync_result, keypoints = sync.synchronise(video_paths, keypoints, clap_times, clap_threshold)
    except sync.ClapNotFoundError as e:
        raise SystemExit(f"{e}\n--sync takes one clap time per video in seconds, e.g. --sync 1.25 0.80 1.10; "
                         f"a video player shows the time. --clap-threshold 0.5 accepts weaker claps.")
    # rewriting an unchanged sync file would make the saved 3D points look stale
    if not sync_from_file:
        io.save_sync(sync_result, str(sync_path))

    print("Clap at " + ", ".join(f"{cid} {t:.3f} s" for cid, t in sync_result.clap_time_s.items()))
    metrics.record("sync.clap_time_s", sync_result.clap_time_s)
    metrics.record("sync.clap_times_from", "given" if clap_times is not None and not sync_from_file
                   else "saved file" if sync_from_file else "audio")
    metrics.record("sync.clap_threshold", float(clap_threshold))
    metrics.record("sync.common_frames", int(len(sync_result.common_timestamps)))
    metrics.record("sync.common_fps", float(config.TARGET_FPS))

    if _stop("sync", stop_after):
        return "sync"

    # Stage 2b: where the cameras are, then real-world units, floor and Y up.
    calib_path = Path(calibration_path)
    if calib_path.exists() and not recalibrate:
        print(f"Using existing calibration {calib_path}")
        rig = io.load_rig(str(calib_path))
        metrics.record("calibrate.reused_file", str(calib_path))

        if len(rig.cameras) != n:
            raise SystemExit(f"{calib_path} has {len(rig.cameras)} cameras but {n} videos were given, "
                             f"add --recalibrate")

    else:
        if performer_height_m is None:
            raise SystemExit("--height-m (performer height in metres) is needed to calibrate")

        with metrics.time("calibrate"):
            rig, from_board = calibrate_cameras(keypoints, video_paths, types, fov, max_error_px, charuco_videos)
            rough_pose = triangulate.triangulate_sequence(keypoints, rig)

            # a board calibration is already in metres, it only needs the floor and Y up
            rig = scale_floor.make_metric(rig, rough_pose, performer_height_m, rescale=not from_board)
        metrics.record("calibrate.from_board", bool(from_board))
        io.save_rig(rig, str(calib_path))

        print(f"Saved calibration to {calib_path}")

    metrics.record("calibrate.reprojection_error_px", rig.reprojection_error_px)
    metrics.record("calibrate.camera_types", dict(zip(ids, types)))

    if _stop("calibrate", stop_after):
        return "calibrate"

    # Stage 2c: final 3D joints. Saved before smoothing, since smoothing is the
    # cheap step most likely to be tuned. Stale if any input file is newer.
    pose_path = paths["pose"]
    inputs = [calib_path, sync_path, *paths["keypoints"].values()]
    if resume and _up_to_date(pose_path, *inputs):
        print(f"Using saved 3D joints from {pose_path.name}")
        pose = io.load_pose3d(str(pose_path))
    else:
        with metrics.time("triangulate"):
            pose = triangulate.triangulate_sequence(keypoints, rig)
        io.save_pose3d(pose, str(pose_path))
    metrics.record("pose_raw", metrics.pose_summary(pose))

    if _stop("triangulate", stop_after):
        return "triangulate"

    if smoothing:
        with metrics.time("smooth"):
            pose = smooth.smooth(smooth.fill_gaps(pose), smoother)
    metrics.record("pose_final", metrics.pose_summary(pose))

    io.save_pose3d_json(pose, out_path, sync_result.common_timestamps)
    print(f"Saved {len(pose.points)} frames of 3D joints to {out_path}")

    # Stage 3: skeleton rig file (.bvh next to the JSON, same name).
    if bvh:
        bvh_path = Path(out_path).with_suffix(".bvh")
        with metrics.time("rig"):
            export_bvh(pose, str(bvh_path))
        print(f"Saved skeleton animation to {bvh_path}")
    return None


def export_bvh(pose, bvh_path: str) -> None:
    """Stage 3: Pose3D -> H36M skeleton with fixed bone lengths -> joint rotations -> .bvh."""
    rig_positions = skeleton.rig_joint_positions(pose)
    metrics.record("rig.bone_lengths", metrics.bone_length_summary(rig_positions, RIG_JOINTS, RIG_PARENTS))
    offsets = skeleton.rest_pose_offsets(skeleton.bone_lengths(rig_positions))
    root_positions, local_rotations = rotations.solve_rotations(rig_positions, offsets)
    euler = rotations.to_euler_degrees(local_rotations, bvh_writer.ROTATION_ORDER)
    bvh_writer.write_bvh(bvh_path, offsets, root_positions, euler, pose.fps)


def per_camera(parser, name, values, n):
    """One value for all cameras, or one per camera."""
    if values is None:
        return None
    if len(values) == 1:
        return values * n
    if len(values) != n:
        parser.error(f"{name} takes one value for all cameras or one per camera ({n}), got {len(values)}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Phone/webcam videos (2 or more cameras) to 3D joints.")
    parser.add_argument("videos", nargs="+",
                        help="One video per camera, at least 2, each starting with a clap. The first is the reference camera.")
    parser.add_argument("--height-m", type=float, default=None,
                        help="Performer height in metres; sets the real-world scale (needed when calibrating).")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="Output JSON path (3D joints per frame). Default: backend/output/out3d.json")
    parser.add_argument("--detector", choices=list(BACKENDS), default=DEFAULT_BACKEND,
                        help=f"Pose model for stage 1 (default: {DEFAULT_BACKEND}). When comparing detectors, also "
                             "pass --recalibrate or a separate --calibration file per detector, otherwise the "
                             "first detector's calibration is reused.")
    parser.add_argument("--model", default=None,
                        help="MediaPipe pose_landmarker .task file (default: MODEL_FILEPATH in .env, or the "
                             "repo's model). Other detectors download their own models.")
    parser.add_argument("--camera", nargs="+", choices=["auto", "iphone", "webcam"], default=["auto"],
                        help="Camera type, one for all or one per video. auto: iPhone if the video has Apple's "
                             "focal length metadata, otherwise webcam (any non-iPhone camera, uses --fov).")
    parser.add_argument("--fov", nargs="+", type=float, default=[config.DEFAULT_HFOV_DEG],
                        help="Horizontal field of view in degrees of the non-iPhone cameras, one for all or one per video.")
    parser.add_argument("--sync", nargs="+", type=float, default=None,
                        help="Clap time in seconds in each video, one per video. Default: found from the audio.")
    parser.add_argument("--clap-threshold", type=float, default=1.0,
                        help="Multiplies how loud a clap must be against the room (default 1.0 = the config values). "
                             "0.5 accepts a clap half as strong; use it when the clap is reported as not loud enough.")
    parser.add_argument("--calibration", default=str(DEFAULT_CALIBRATION),
                        help="Calibration file, reused if it exists. Default: backend/output/calibration.json")
    parser.add_argument("--recalibrate", action="store_true", help="Ignore an existing calibration file.")
    parser.add_argument("--max-error", type=float, default=config.CALIB_MAX_ERROR_PX,
                        help="Calibration above this reprojection error (px) falls back to the ChArUco board.")
    parser.add_argument("--charuco-videos", nargs="+", default=None,
                        help="Board video from each camera, used only if calibration from the performer fails.")
    parser.add_argument("--smoother", choices=list(smooth.SMOOTHERS), default=config.SMOOTHER,
                        help=f"Stage 2c filter (default: {config.SMOOTHER}). savgol: Savitzky-Golay, "
                             f"{config.SMOOTH_WINDOW_FRAMES}-frame window. butterworth: zero-phase low-pass at "
                             f"{config.BUTTER_CUTOFF_HZ:g} Hz. Runs even with --resume, so two resumed runs compare them.")
    parser.add_argument("--no-smooth", action="store_true", help="Skip gap filling and smoothing.")
    parser.add_argument("--no-bvh", action="store_true",
                        help="Skip the skeleton animation (.bvh written next to the --out JSON).")
    parser.add_argument("--resume", action="store_true",
                        help="Reuse the stage files saved next to --out from an earlier run (joints, clap "
                             "times, 3D points) instead of recomputing them. Changed videos are detected.")
    parser.add_argument("--stop-after", choices=STAGES, default=None,
                        help="Run up to this stage, save its file next to --out, and stop.")
    args = parser.parse_args()

    n = len(args.videos)
    if n < config.MIN_CAMERAS:
        parser.error(f"give at least {config.MIN_CAMERAS} videos, one per camera (got {n})")
    if args.sync is not None and len(args.sync) != n:
        parser.error(f"--sync needs one clap time per video ({n})")
    if args.charuco_videos and len(args.charuco_videos) != n:
        parser.error(f"--charuco-videos needs one board video per camera ({n})")

    run(args.videos, args.out, performer_height_m=args.height_m, model_path=args.model,
        camera=per_camera(parser, "--camera", args.camera, n), fov=per_camera(parser, "--fov", args.fov, n),
        clap_times=args.sync, calibration_path=args.calibration, recalibrate=args.recalibrate,
        max_error_px=args.max_error, charuco_videos=args.charuco_videos, smoothing=not args.no_smooth,
        bvh=not args.no_bvh, resume=args.resume, stop_after=args.stop_after,
        detector=args.detector, smoother=args.smoother, clap_threshold=args.clap_threshold)


if __name__ == "__main__":
    main()
