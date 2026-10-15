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

from ..joints import JOINT_INDEX, NUM_JOINTS

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


# Halpe-26 keypoint order, as RTMPose's body-with-feet models output it.
HALPE26_JOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
    "head", "neck", "hip",
    "left_big_toe", "right_big_toe", "left_small_toe", "right_small_toe",
    "left_heel", "right_heel",
]

# MediaPipe joint -> the Halpe-26 joint that fills it. Left/right are the
# performer's own in both formats. MediaPipe joints missing here (inner/outer
# eyes, mouth, fingers) stay NaN; none of them are used by stages 2 and 3.
# Approximation: MediaPipe's FOOT_INDEX is the tip of the foot, filled from
# the big toe, the nearest Halpe-26 point (scale_floor only uses it to find
# the floor).
MEDIAPIPE_FROM_HALPE26 = {
    "NOSE": "nose",
    "LEFT_EYE": "left_eye", "RIGHT_EYE": "right_eye",
    "LEFT_EAR": "left_ear", "RIGHT_EAR": "right_ear",
    "LEFT_SHOULDER": "left_shoulder", "RIGHT_SHOULDER": "right_shoulder",
    "LEFT_ELBOW": "left_elbow", "RIGHT_ELBOW": "right_elbow",
    "LEFT_WRIST": "left_wrist", "RIGHT_WRIST": "right_wrist",
    "LEFT_HIP": "left_hip", "RIGHT_HIP": "right_hip",
    "LEFT_KNEE": "left_knee", "RIGHT_KNEE": "right_knee",
    "LEFT_ANKLE": "left_ankle", "RIGHT_ANKLE": "right_ankle",
    "LEFT_HEEL": "left_heel", "RIGHT_HEEL": "right_heel",
    "LEFT_FOOT_INDEX": "left_big_toe", "RIGHT_FOOT_INDEX": "right_big_toe",
}
_MP_SLOTS = np.array([JOINT_INDEX[mp_name] for mp_name in MEDIAPIPE_FROM_HALPE26])
_HALPE_SLOTS = np.array([HALPE26_JOINTS.index(h) for h in MEDIAPIPE_FROM_HALPE26.values()])


def halpe26_to_mediapipe(keypoints: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    One person's Halpe-26 output -> MediaPipe-order points and confidence.

    keypoints : (26, 2) pixels.  scores : (26,) RTMPose scores.
    RTMPose scores are not probabilities like MediaPipe's visibility; they are
    clipped to 0..1 here so the config.py thresholds can be applied, but those
    thresholds were tuned on MediaPipe (check the score spread on real takes).
    A joint scored 0 or less has no valid location and becomes NaN.
    """
    points, confidence = empty_frame()
    points[_MP_SLOTS] = keypoints[_HALPE_SLOTS]
    confidence[_MP_SLOTS] = np.clip(scores[_HALPE_SLOTS], 0.0, 1.0)
    points[confidence <= 0] = np.nan
    return points, confidence


def pick_person(bboxes: np.ndarray) -> int | None:
    """
    Index of the performer among the detected people: the largest box.
    None if nobody was detected. bboxes are (N, 4) x1, y1, x2, y2 pixels.
    """
    if len(bboxes) == 0:
        return None
    areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
    return int(np.argmax(areas))


class RTMPoseBackend(PoseBackend):
    """
    RTMPose with the Halpe-26 (body with feet) model, through rtmlib
    (github.com/Tau-J/rtmlib, Apache-2.0) on ONNX Runtime.

    Unlike MediaPipe it does not track: every frame a person detector (YOLOX)
    finds the people, the largest one is taken as the performer
    (pick_person) and RTMPose finds that person's 26 joints. rtmlib downloads
    both models on first use (into ~/.cache), so model_path is not used.

    mode: rtmlib's "lightweight", "balanced" or "performance" (slower, more
    accurate). device: "cpu" or "cuda" (needs onnxruntime-gpu).
    """
    name = "rtmpose"

    def __init__(self, model_path: str | None = None, mode: str = "balanced", device: str = "cpu"):
        from rtmlib import BodyWithFeet

        self._model = BodyWithFeet(mode=mode, backend="onnxruntime", device=device)

    def detect(self, rgb, frame_ms):
        import cv2

        # rtmlib is written for OpenCV's BGR frames (its examples feed cap.read() directly)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        bboxes = np.asarray(self._model.det_model(bgr)).reshape(-1, 4)
        person = pick_person(bboxes)
        if person is None:
            # without a box rtmlib would run the pose model on the whole image
            # and always "find" someone, so no detection means no person
            return empty_frame()

        keypoints, scores = self._model.pose_model(bgr, bboxes=[bboxes[person]])
        return halpe26_to_mediapipe(keypoints[0], scores[0])


# Detector name (what run_pipeline's --detector will take) -> backend class.
BACKENDS: dict[str, type[PoseBackend]] = {
    MediaPipeBackend.name: MediaPipeBackend,
    RTMPoseBackend.name: RTMPoseBackend,
}


def create_backend(name: str = DEFAULT_BACKEND, model_path: str | None = None) -> PoseBackend:
    """Build the backend registered under name. model_path is ignored by models that bring their own."""
    try:
        backend_class = BACKENDS[name]
    except KeyError:
        raise ValueError(f"Unknown pose detector {name!r}, choose from: {', '.join(BACKENDS)}") from None
    return backend_class(model_path=model_path)
