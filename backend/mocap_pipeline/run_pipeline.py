"""
Command line entry point: runs every stage in order.

    cd backend
    python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV cam2.mp4 --height-m 1.75 --out take01.json

This file is the one place that knows the order of the stages. When the web
backend is built later, it should call run() rather than repeat this logic.
"""
from __future__ import annotations
import argparse
import os
import numpy as np

from pathlib import Path
from . import config, io
from .stage1_keypoints import detect
from .stage2_reconstruct import calibrate, scale_floor, smooth, sync, triangulate
from .stage3_rig import bvh_writer, rotations, skeleton
from .stage2_reconstruct.iphone_camera import (is_iphone_video, iphone_intrinsics, IPhoneMetadataError,
                                               MODEL_KEY)

BACKEND_DIR = Path(__file__).resolve().parent.parent
# where results go unless --out / --calibration say otherwise (created when needed)
OUTPUT_DIR = BACKEND_DIR / "output"
DEFAULT_OUT = OUTPUT_DIR / "out3d.json"
DEFAULT_CALIBRATION = OUTPUT_DIR / "calibration.json"


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


def run(video_paths: list[str], out_path: str, performer_height_m: float | None = None,
        model_path: str | None = None, camera: list[str] | None = None, fov: list[float] | None = None,
        clap_times: list[float] | None = None, calibration_path: str = str(DEFAULT_CALIBRATION),
        recalibrate: bool = False, max_error_px: float = config.CALIB_MAX_ERROR_PX,
        charuco_videos: list[str] | None = None, smoothing: bool = True, bvh: bool = True) -> None:
    
    n = len(video_paths)

    if not config.MIN_CAMERAS <= n <= config.MAX_CAMERAS:
        raise ValueError(f"Give {config.MIN_CAMERAS} to {config.MAX_CAMERAS} videos, one per camera (got {n}).")
    
    model_path = model_path or default_model_path()
    camera = camera or ["auto"] * n
    fov = fov or [config.DEFAULT_HFOV_DEG] * n

    types = camera_types(video_paths, camera)
    print("Cameras: " + ", ".join(f"cam{c} {kind}" for c, kind in enumerate(types)))

    # Stage 1: 2D joints per camera.
    keypoints = []
    for video in video_paths:
        print(f"Detecting joints in {video}")
        keypoints.append(detect.detect_video(video, model_path))

    # camera ids must be unique (two videos can share a file name in different folders)
    if len({kp.camera_id for kp in keypoints}) < n:
        for c, kp in enumerate(keypoints):
            kp.camera_id = f"cam{c}_{kp.camera_id}"

    # Stage 2a: one shared clock.
    try:
        sync_result, keypoints = sync.synchronise(video_paths, keypoints, clap_times)
    except sync.ClapNotFoundError as e:
        raise SystemExit(f"{e}\nGive the clap time in each video by hand with --sync T0 T1 ... (seconds)")
    
    print("Clap at " + ", ".join(f"{cid} {t:.3f} s" for cid, t in sync_result.clap_time_s.items()))

    # Stage 2b: where the cameras are, then real-world units, floor and Y up.
    calib_path = Path(calibration_path)
    if calib_path.exists() and not recalibrate:
        print(f"Using existing calibration {calib_path}")
        rig = io.load_rig(str(calib_path))

        if len(rig.cameras) != n:
            raise SystemExit(f"{calib_path} has {len(rig.cameras)} cameras but {n} videos were given, "
                             f"add --recalibrate")
        
    else:
        if performer_height_m is None:
            raise SystemExit("--height-m (performer height in metres) is needed to calibrate")
        
        rig, from_board = calibrate_cameras(keypoints, video_paths, types, fov, max_error_px, charuco_videos)
        rough_pose = triangulate.triangulate_sequence(keypoints, rig)

        # a board calibration is already in metres, it only needs the floor and Y up
        rig = scale_floor.make_metric(rig, rough_pose, performer_height_m, rescale=not from_board)
        calib_path.parent.mkdir(parents=True, exist_ok=True)
        io.save_rig(rig, str(calib_path))

        print(f"Saved calibration to {calib_path}")

    # Stage 2c: final 3D joints.
    pose = triangulate.triangulate_sequence(keypoints, rig)
    
    if smoothing:
        pose = smooth.smooth(smooth.fill_gaps(pose))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    io.save_pose3d_json(pose, out_path, sync_result.common_timestamps)
    print(f"Saved {len(pose.points)} frames of 3D joints to {out_path}")

    # Stage 3: skeleton rig file (.bvh next to the JSON, same name).
    if bvh:
        bvh_path = Path(out_path).with_suffix(".bvh")
        export_bvh(pose, str(bvh_path))
        print(f"Saved skeleton animation to {bvh_path}")

    # TODO: save every intermediate result with io.py next to out_path so a
    # failed run can be inspected and resumed from the last good stage.


def export_bvh(pose, bvh_path: str) -> None:
    """Stage 3: Pose3D -> H36M skeleton with fixed bone lengths -> joint rotations -> .bvh."""
    rig_positions = skeleton.rig_joint_positions(pose)
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
    parser = argparse.ArgumentParser(description="Phone/webcam videos (2-4 cameras) to 3D joints.")
    parser.add_argument("videos", nargs="+",
                        help="One video per camera, 2 to 4, each starting with a clap. The first is the reference camera.")
    parser.add_argument("--height-m", type=float, default=None,
                        help="Performer height in metres; sets the real-world scale (needed when calibrating).")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="Output JSON path (3D joints per frame). Default: backend/output/out3d.json")
    parser.add_argument("--model", default=None,
                        help="pose_landmarker .task file (default: MODEL_FILEPATH in .env, or the repo's model)")
    parser.add_argument("--camera", nargs="+", choices=["auto", "iphone", "webcam"], default=["auto"],
                        help="Camera type, one for all or one per video. auto: iPhone if the video has Apple's "
                             "focal length metadata, otherwise webcam (any non-iPhone camera, uses --fov).")
    parser.add_argument("--fov", nargs="+", type=float, default=[config.DEFAULT_HFOV_DEG],
                        help="Horizontal field of view in degrees of the non-iPhone cameras, one for all or one per video.")
    parser.add_argument("--sync", nargs="+", type=float, default=None,
                        help="Clap time in seconds in each video, one per video. Default: found from the audio.")
    parser.add_argument("--calibration", default=str(DEFAULT_CALIBRATION),
                        help="Calibration file, reused if it exists. Default: backend/output/calibration.json")
    parser.add_argument("--recalibrate", action="store_true", help="Ignore an existing calibration file.")
    parser.add_argument("--max-error", type=float, default=config.CALIB_MAX_ERROR_PX,
                        help="Calibration above this reprojection error (px) falls back to the ChArUco board.")
    parser.add_argument("--charuco-videos", nargs="+", default=None,
                        help="Board video from each camera, used only if calibration from the performer fails.")
    parser.add_argument("--no-smooth", action="store_true", help="Skip gap filling and smoothing.")
    parser.add_argument("--no-bvh", action="store_true",
                        help="Skip the skeleton animation (.bvh written next to the --out JSON).")
    args = parser.parse_args()

    n = len(args.videos)
    if not config.MIN_CAMERAS <= n <= config.MAX_CAMERAS:
        parser.error(f"give {config.MIN_CAMERAS} to {config.MAX_CAMERAS} videos, one per camera (got {n})")
    if args.sync is not None and len(args.sync) != n:
        parser.error(f"--sync needs one clap time per video ({n})")
    if args.charuco_videos and len(args.charuco_videos) != n:
        parser.error(f"--charuco-videos needs one board video per camera ({n})")

    run(args.videos, args.out, performer_height_m=args.height_m, model_path=args.model,
        camera=per_camera(parser, "--camera", args.camera, n), fov=per_camera(parser, "--fov", args.fov, n),
        clap_times=args.sync, calibration_path=args.calibration, recalibrate=args.recalibrate,
        max_error_px=args.max_error, charuco_videos=args.charuco_videos, smoothing=not args.no_smooth,
        bvh=not args.no_bvh)


if __name__ == "__main__":
    main()
