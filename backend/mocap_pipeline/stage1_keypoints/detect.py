"""
Stage 1: run the pose model on every frame of one video.

Starting point: backend/landmarks_from_image_test/ already does this for a
single image (detector.py, main.py). This module is the video version.

Input : path to one phone's video.
Output: schemas.Keypoints2D for that camera.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

from ..joints import NUM_JOINTS
from ..schemas import Keypoints2D


def create_landmarker(model_path: str):
    """
    Build the MediaPipe PoseLandmarker in VIDEO mode.

    Same options as landmarks_from_image_test/detector.py, but
    running_mode=VIDEO so MediaPipe tracks the person between frames, and
    num_poses=1 (single performer). Segmentation masks are not needed.
    """
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1)
    return vision.PoseLandmarker.create_from_options(options)


def detect_video(video_path: str, model_path: str) -> Keypoints2D:
    """
    Every frame of one video -> pixel joints + confidence + real timestamps.

    Frames with no person get NaN points and 0 confidence; no frame is ever
    dropped, so the arrays stay aligned with timestamps. Low-confidence joints
    are kept (with their confidence), later stages decide what to ignore.
    """

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = 0   # set to 0 for now, will be updated later!
    height = 0  # set to 0 for now, will be updated later!

    points, confidence, timestamps = [], [], []

    with create_landmarker(model_path) as landmarker:
        frame_idx = 0
        last_ms = -1

        while True:     # while video can still be read, continues
            ok, frame = cap.read()
            if not ok:
                break

            # calculates based from decoded frame
            height, width = frame.shape[:2]

            # real time of this frame, read right after cap.read()
            frame_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

            if frame_ms <= 0 and frame_idx > 0:
                frame_ms = frame_idx * 1000.0 / fps

            timestamps.append(frame_ms / 1000.0)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # VIDEO mode needs a strictly increasing timestamp in ms
            timestamp_ms = max(int(round(frame_ms)), last_ms + 1)
            last_ms = timestamp_ms
            result = landmarker.detect_for_video(image, timestamp_ms)

            frame_pts = np.full((NUM_JOINTS, 2), np.nan)
            frame_conf = np.zeros(NUM_JOINTS)
            
            if result.pose_landmarks:
                for i, lm in enumerate(result.pose_landmarks[0]):
                    # pose_landmarks are 0-1 of the image, convert to pixels;
                    # MediaPipe's z is a per-camera guess, stage 2 computes real depth
                    frame_pts[i] = (lm.x * width, lm.y * height)
                    frame_conf[i] = lm.visibility if lm.visibility is not None else 1.0

            points.append(frame_pts)
            confidence.append(frame_conf)
            frame_idx += 1

    cap.release()

    if frame_idx == 0:
        raise ValueError(f"No frames could be read from video: {video_path}")

    return Keypoints2D(
        camera_id=Path(video_path).stem,
        video_path=str(video_path),
        width=width,
        height=height,
        fps=fps,
        timestamps=np.array(timestamps),
        points=np.array(points).reshape(-1, NUM_JOINTS, 2),
        confidence=np.array(confidence).reshape(-1, NUM_JOINTS),
    )
