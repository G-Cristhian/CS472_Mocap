"""
Stage 1: run the pose model on every frame of one video.

Starting point: backend/landmarks_from_image_test/ already does this for a
single image (detector.py, main.py). This module is the video version.

Input : path to one phone's video.
Output: schemas.Keypoints2D for that camera.
"""
from __future__ import annotations

from ..schemas import Keypoints2D


def create_landmarker(model_path: str):
    """
    Build the MediaPipe PoseLandmarker in VIDEO mode.

    TODO:
      1. Same options as landmarks_from_image_test/detector.py, but set
         running_mode=VIDEO so MediaPipe tracks the person between frames.
      2. num_poses=1 (single performer). Segmentation masks are not needed.
    """
    raise NotImplementedError


def detect_video(video_path: str, model_path: str) -> Keypoints2D:
    """
    TODO:
      1. Open the video with cv2.VideoCapture. Read width, height, fps.
         Respect the rotation flag: phone videos are often stored sideways.
      2. For each frame: read its real timestamp (CAP_PROP_POS_MSEC, since
         phones record variable frame rate), convert BGR -> RGB, call
         landmarker.detect_for_video(image, timestamp_ms).
      3. Use result.pose_landmarks (normalised image coordinates), NOT
         pose_world_landmarks. Multiply x by width and y by height to get
         pixels. Store the landmark's visibility as confidence.
         Discard MediaPipe's z: it is a per-camera guess, stage 2 computes
         real depth.
      4. Frames with no person detected: fill that frame with NaN points and
         0 confidence. Never drop the frame, the arrays must stay aligned
         with timestamps.
      5. Return Keypoints2D with camera_id = the video file's stem.
    """
    raise NotImplementedError
