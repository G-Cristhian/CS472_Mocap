import argparse
import os
from pathlib import Path

from aniposelib.cameras import CameraGroup
from dotenv import load_dotenv
from extract_2d import extract_2d, stack_cameras, stack_cameras_by_time, LANDMARK_NAMES
from calibrate_person import calibrate_from_person, guess_intrinsics, PersonCalibrationError
from iphone_camera import is_iphone_video, iphone_intrinsics, IPhoneMetadataError, MODEL_KEY
from triangulate import triangulate_3d, save_json

load_dotenv()

MIN_CAMERAS, MAX_CAMERAS = 2, 4

def parse_args():
    parser = argparse.ArgumentParser(description="Multi-camera (2-4) MediaPipe -> 3D landmarks")
    parser.add_argument("videos", nargs="+", help="motion video from each camera (cam0 cam1 ...), 2 to 4 videos")
    parser.add_argument("--model", default=os.path.expanduser(os.getenv("MODEL_FILEPATH", "")),
                        help="pose_landmarker .task file (or MODEL_FILEPATH in .env)")
    parser.add_argument("--scale", nargs=3, metavar=("LANDMARK_A", "LANDMARK_B", "METERS"),
                        default=["LEFT_SHOULDER", "RIGHT_SHOULDER", "0.36"],
                        help="a body length measured on the subject, sets real-world units")
    parser.add_argument("--camera", nargs="+", choices=["auto", "iphone", "webcam"], default=["auto"],
                        help="camera type, one for all or one per video. auto: iPhone if the video has "
                             "Apple's focal length metadata, otherwise webcam (any non-iPhone camera, uses --fov)")
    parser.add_argument("--fov", nargs="+", type=float, default=[65.0],
                        help="horizontal field of view in degrees of the non-iPhone cameras, one for all or one per video")
    parser.add_argument("--offsets", nargs="+", type=int, default=None,
                        help="frames to skip at the start of each video to sync them (all-webcam setups only)")
    parser.add_argument("--sync", nargs="+", type=float, default=None,
                        help="seconds into each video of the same moment, e.g. a clap "
                             "(used when any camera is an iPhone, frames are matched by time)")
    parser.add_argument("--calibration", default="calibration.toml",
                        help="calibration file, reused if it exists")
    parser.add_argument("--recalibrate", action="store_true", help="ignore an existing calibration file")
    parser.add_argument("--max-error", type=float, default=10.0,
                        help="person calibration above this reprojection error (px) falls back to ChArUco")
    parser.add_argument("--charuco-videos", nargs="+", default=None,
                        help="board video from each camera, used only if person calibration fails")
    parser.add_argument("--out", default="out3d.json")
    args = parser.parse_args()

    n = len(args.videos)
    if not MIN_CAMERAS <= n <= MAX_CAMERAS:
        parser.error(f"give {MIN_CAMERAS} to {MAX_CAMERAS} videos, one per camera (got {n})")
    args.camera = per_camera(parser, "--camera", args.camera, n)
    args.fov = per_camera(parser, "--fov", args.fov, n)
    args.offsets = per_camera(parser, "--offsets", args.offsets or [0], n)
    args.sync = per_camera(parser, "--sync", args.sync or [0.0], n)
    if args.charuco_videos and len(args.charuco_videos) != n:
        parser.error(f"--charuco-videos needs one board video per camera ({n})")

    return args

# command-line function to take either a single value for all cameras, or a unique value for each
def per_camera(parser, name, values, n):
    if len(values) == 1:
        return values * n
    if len(values) != n:
        parser.error(f"{name} takes one value for all cameras or one per camera ({n}), got {len(values)}")

    return values

# function to grab camera type (iPhone or webcam) for each video from video metadata
#   --camera argument is used by specify which bypasses guess
def camera_types(args):
    types = []
    for video, choice in zip(args.videos, args.camera):
        if choice == "auto":
            choice = "iphone" if is_iphone_video(video) else "webcam"
        types.append(choice)

    return types

# function to create a camera matrix for each camera
#   iPhones from metadata
#   Other cameras guessed from --fov
def camera_intrinsics(args, types, sizes):
    intrinsics = []

    for video, kind, size, fov in zip(args.videos, types, sizes, args.fov):
        if kind == "iphone":
            try:
                K, metadata = iphone_intrinsics(video, size)
                print(f"{video}: {metadata.get(MODEL_KEY, 'iPhone')}, focal length {K[0, 0]:.0f} px from metadata")
                intrinsics.append(K)
                continue
            except IPhoneMetadataError as e:
                print(f"{e}\nFalling back to --fov {fov} for this camera")

        intrinsics.append(guess_intrinsics(size, fov))

    return intrinsics

def calibrate(args, points, sizes, intrinsics):
    name_a, name_b, length = args.scale
    if name_a not in LANDMARK_NAMES or name_b not in LANDMARK_NAMES:
        raise SystemExit(f"--scale landmarks must be MediaPipe names, e.g. LEFT_SHOULDER")

    try:
        cgroup, info = calibrate_from_person(points, sizes, (name_a, name_b, float(length)),
                                             intrinsics=intrinsics)
        print(f"Person calibration: {info['reprojection_error_px']:.2f} px error, "
              f"{info['correspondences']} matched landmarks, started from cameras {info['start_pair']}")
        if info["reprojection_error_px"] <= args.max_error:
            return cgroup
        reason = f"error {info['reprojection_error_px']:.2f} px is above --max-error {args.max_error}"

    except PersonCalibrationError as e:
        reason = str(e)

    # if default method fails accuracy check, load the board! (fallback method)
    if not args.charuco_videos:
        boards = " ".join(f"cam{c}_board.mp4" for c in range(len(args.videos)))
        raise SystemExit(f"Person calibration failed ({reason}).\n"
                         f"Record the ChArUco board with every camera and rerun with --charuco-videos {boards}")

    print(f"Person calibration failed ({reason}), falling back to ChArUco board")

    from board_calibration import calibrate_from_board
    cgroup, info = calibrate_from_board(args.charuco_videos)

    print(f"ChArUco calibration: {info['reprojection_error_px']:.2f} px error")

    return cgroup

def main():
    args = parse_args()

    types = camera_types(args)
    print("Cameras: " + ", ".join(f"cam{c} {kind}" for c, kind in enumerate(types)))
    # iPhones record at a variable frame rate and mixed cameras rarely share one exactly,
    # so as soon as an iPhone is involved, match frames by time instead of frame number
    by_time = "iphone" in types

    results = []

    for video in args.videos:
        print(f"Detecting landmarks in {video}")
        results.append(extract_2d(video, args.model, video_times=by_time))

    times = None

    if by_time:
        points, times = stack_cameras_by_time(results, args.sync)
    else:
        points = stack_cameras(results, args.offsets)

    sizes = [r["size"] for r in results]

    calib_path = Path(args.calibration)

    if calib_path.exists() and not args.recalibrate:
        print(f"Using existing calibration {calib_path}")
        cgroup = CameraGroup.load(str(calib_path))

        if len(cgroup.cameras) != len(args.videos):
            raise SystemExit(f"{calib_path} has {len(cgroup.cameras)} cameras but {len(args.videos)} videos "
                             f"were given, add --recalibrate")
    else:
        cgroup = calibrate(args, points, sizes, camera_intrinsics(args, types, sizes))
        cgroup.dump(str(calib_path))
        print(f"Saved calibration to {calib_path}")

    p3ds = triangulate_3d(cgroup, points)
    save_json(p3ds, results[0]["fps"], args.out, times=times)
    print(f"Saved {len(p3ds)} frames of 3D landmarks to {args.out}")

if __name__ == "__main__":
    main()
