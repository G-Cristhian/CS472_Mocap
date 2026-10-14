"""
Stage 1 pose models behind one interface, so the pipeline can switch models.

A backend turns one RGB video frame into the 33 MediaPipe joints
(joints.MEDIAPIPE_JOINTS order): pixel x, y plus a 0..1 confidence per joint.
Joints a model does not have stay NaN with confidence 0. Stages 2 and 3 only
ever see that, so adding a model means writing one class here and adding it
to BACKENDS. detect.py handles reading the video; backends only see frames.
"""
from __future__ import annotations

import numpy as np

from ..joints import NUM_JOINTS

DEFAULT_BACKEND = "mediapipe"


def empty_frame() -> tuple[np.ndarray, np.ndarray]:
    """A frame with no person: NaN points, 0 confidence."""
    return np.full((NUM_JOINTS, 2), np.nan), np.zeros(NUM_JOINTS)


class PoseBackend:
    """
    One pose model. Use it as a context manager so the model is released:

        with create_backend("mediapipe", model_path) as backend:
            points, confidence = backend.detect(rgb, frame_ms)

    Frames must be given in order, one video per backend instance (some models
    track the person from frame to frame).
    """
    name = ""

    def __enter__(self) -> "PoseBackend":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Release the model. Override if the model holds resources."""

    def detect(self, rgb: np.ndarray, frame_ms: float) -> tuple[np.ndarray, np.ndarray]:
        """
        rgb      : (H, W, 3) uint8 frame, RGB order.
        frame_ms : time of this frame in the video, milliseconds.
        Returns (points (33, 2) pixels, confidence (33,) 0..1), see empty_frame().
        """
        raise NotImplementedError


class MediaPipeBackend(PoseBackend):
    """
    MediaPipe PoseLandmarker in VIDEO mode, so it tracks the person between
    frames, with num_poses=1 (single performer). Same options as
    landmarks_from_image_test/detector.py. Segmentation masks are not needed.
    """
    name = "mediapipe"

    def __init__(self, model_path: str | None = None):
        if not model_path:
            raise ValueError("The MediaPipe backend needs a pose_landmarker .task model file")

        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1)
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._last_ms = -1

    def close(self) -> None:
        self._landmarker.close()

    def detect(self, rgb, frame_ms):
        import mediapipe as mp

        height, width = rgb.shape[:2]
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # VIDEO mode needs a strictly increasing timestamp in ms
        timestamp_ms = max(int(round(frame_ms)), self._last_ms + 1)
        self._last_ms = timestamp_ms
        result = self._landmarker.detect_for_video(image, timestamp_ms)

        points, confidence = empty_frame()
        if result.pose_landmarks:
            for i, lm in enumerate(result.pose_landmarks[0]):
                # pose_landmarks are 0-1 of the image, convert to pixels;
                # MediaPipe's z is a per-camera guess, stage 2 computes real depth
                points[i] = (lm.x * width, lm.y * height)
                confidence[i] = lm.visibility if lm.visibility is not None else 1.0
        return points, confidence


# Detector name (what run_pipeline's --detector will take) -> backend class.
BACKENDS: dict[str, type[PoseBackend]] = {
    MediaPipeBackend.name: MediaPipeBackend,
}


def create_backend(name: str = DEFAULT_BACKEND, model_path: str | None = None) -> PoseBackend:
    """Build the backend registered under name. model_path is ignored by models that bring their own."""
    try:
        backend_class = BACKENDS[name]
    except KeyError:
        raise ValueError(f"Unknown pose detector {name!r}, choose from: {', '.join(BACKENDS)}") from None
    return backend_class(model_path=model_path)
