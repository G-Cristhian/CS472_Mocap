import cv2
import numpy as np
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# names of the 33 MediaPipe pose landmarks, in index order

# names of 33 MediaPipe pose landmarks
#   ordered by index!
LANDMARK_NAMES = [lm.name for lm in vision.PoseLandmark]
N_LANDMARKS = len(LANDMARK_NAMES)

# video_times: use each frame's real timestamp from the file instead of frame_idx / fps,
#   for variable frame rate videos like iPhones (see stack_cameras_by_time)

# function that runs MediaPipe on every frame of a camera's video!
#   returns pixel coords with NaN where landmark is missing / not visible enough
def extract_2d(video_path, model_path, min_visibility=0.5, video_times=False):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1)

    points = []
    visibility = []
    times = []

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        frame_idx = 0
        last_ms = -1

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # calculates based from decoded frame
            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            frame_ms = frame_idx * 1000.0 / fps

            if video_times:
                # real time of this frame, read right after cap.read()
                pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

                if pos_ms > 0 or frame_idx == 0:
                    frame_ms = pos_ms

            times.append(frame_ms / 1000.0)

            # VIDEO mode needs a strictly increasing timestamp in ms
            timestamp_ms = max(int(round(frame_ms)), last_ms + 1)
            last_ms = timestamp_ms

            result = landmarker.detect_for_video(image, timestamp_ms)

            frame_pts = np.full((N_LANDMARKS, 2), np.nan)
            frame_vis = np.zeros(N_LANDMARKS)

            if result.pose_landmarks:
                for i, lm in enumerate(result.pose_landmarks[0]):
                    frame_vis[i] = lm.visibility if lm.visibility is not None else 1.0
                    if frame_vis[i] >= min_visibility:
                        # pose_landmarks are 0-1 of the image, convert to pixels
                        frame_pts[i] = (lm.x * width, lm.y * height)

            points.append(frame_pts)
            visibility.append(frame_vis)
            frame_idx += 1

    cap.release()

    return {
        "points": np.array(points).reshape(-1, N_LANDMARKS, 2),
        "visibility": np.array(visibility).reshape(-1, N_LANDMARKS),
        "times": np.array(times),
        "size": (width, height),
        "fps": fps,
    }

# function that stacks cameras into the expected array format for aniposelib
#   offset shifts a camera by whole frames if videos started at different times!
def stack_cameras(results, offsets=None):
    offsets = offsets or [0] * len(results)
    trimmed = [r["points"][o:] for r, o in zip(results, offsets)]
    n_frames = min(len(t) for t in trimmed)
    return np.stack([t[:n_frames] for t in trimmed])

# function to match frames across cameras by time rather than by frame number
#   using variable frame rate for iPhones
#   calculating for mixed cameras (where frame rates don't match exactly)
#   camera with lowest frame rate is reference to ensure a match for every camera
#   RETURNS points in (n_cams, n_frames, 33, 2) format, and reference times in seconds (0 is sync moment)
def stack_cameras_by_time(results, sync_times):
    ref = min(range(len(results)), key=lambda c: results[c]["fps"])
    ref_times = results[ref]["times"] - sync_times[ref]
    keep = np.ones(len(ref_times), dtype=bool)
    matched = []

    for c, (r, sync) in enumerate(zip(results, sync_times)):
        if c == ref:
            matched.append(r["points"])
            continue

        times = r["times"] - sync

        if len(times) < 2:
            raise ValueError(f"camera {c} has too few frames")
        
        # drop reference frames from before this camera started or after it stopped
        keep &= (ref_times >= times[0]) & (ref_times <= times[-1])

        # nearest frame in time, look at the frames on either side of each reference time
        idx = np.clip(np.searchsorted(times, ref_times), 1, len(times) - 1)
        before, after = times[idx - 1], times[idx]
        idx = np.where(np.abs(ref_times - before) <= np.abs(after - ref_times), idx - 1, idx)
        gap = np.abs(times[idx] - ref_times)

        points = r["points"][idx].copy()
        
        # no frame within half a frame of the reference time, likely a dropped frame
        points[gap > 0.5 / r["fps"]] = np.nan
        matched.append(points)

    return np.stack(matched)[:, keep], ref_times[keep]
