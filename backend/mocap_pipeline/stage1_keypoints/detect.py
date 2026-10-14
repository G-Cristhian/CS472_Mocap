"""
Stage 1: run a pose model on every frame of one video.

Starting point: backend/landmarks_from_image_test/ already does this for a
single image (detector.py, main.py). This module is the video version.

The model itself lives in backends.py (MediaPipe by default); this module
reads the video and builds the arrays, the same for every model.

Input : path to one phone's video.
Output: schemas.Keypoints2D for that camera.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..joints import NUM_JOINTS
from ..schemas import Keypoints2D
from .backends import DEFAULT_BACKEND, create_backend


def detect_video(video_path: str, model_path: str, detector: str = DEFAULT_BACKEND) -> Keypoints2D:
    """
    Every frame of one video -> pixel joints + confidence + real timestamps.

    detector picks the pose model (a name in backends.BACKENDS); model_path
    is the model file for detectors that need one (MediaPipe's .task file).

    Frames with no person get NaN points and 0 confidence; no frame is ever
    dropped, so the arrays stay aligned with timestamps. Low-confidence joints
    are kept (with their confidence), later stages decide what to ignore.
    """

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    points, confidence, timestamps = [], [], []

    with create_backend(detector, model_path) as backend:
        frame_idx = 0
        while True:
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
            frame_pts, frame_conf = backend.detect(rgb, frame_ms)

            points.append(frame_pts)
            confidence.append(frame_conf)
            frame_idx += 1

    cap.release()

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
