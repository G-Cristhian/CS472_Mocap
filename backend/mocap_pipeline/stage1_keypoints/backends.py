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

from .. import config
from ..joints import JOINT_INDEX, MEDIAPIPE_JOINTS, NUM_JOINTS

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
    # the joints (MediaPipe names) this model can find; None means all of them.
    # The others are NaN in every frame by design, not missed detections.
    joints: tuple[str, ...] | None = None

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
    legacy/landmarks_from_image_test/detector.py. Segmentation masks are not needed.
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


def box_from_joints(keypoints: np.ndarray, scores: np.ndarray, width: int, height: int) -> np.ndarray | None:
    """
    The box to look for the performer in on the next frame, from this frame's
    Halpe-26 joints: the joints scoring at least config.RTMPOSE_TRACK_MIN_SCORE,
    their bounding box grown config.RTMPOSE_TRACK_BOX_SCALE times about its
    centre, kept inside the image. None if fewer than
    config.RTMPOSE_TRACK_MIN_JOINTS joints qualify (performer lost or
    occluded), which sends the next frame back to the person detector.
    """
    good = (scores >= config.RTMPOSE_TRACK_MIN_SCORE) & np.isfinite(keypoints).all(axis=1)
    if good.sum() < config.RTMPOSE_TRACK_MIN_JOINTS:
        return None
    pts = keypoints[good]
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    centre, half = (lo + hi) / 2, (hi - lo) / 2 * config.RTMPOSE_TRACK_BOX_SCALE
    x1, y1 = np.maximum(centre - half, 0)
    x2, y2 = np.minimum(centre + half, [width - 1, height - 1])
    if x2 <= x1 or y2 <= y1:
        return None
    return np.array([x1, y1, x2, y2])


def pick_person(bboxes: np.ndarray) -> int | None:
    """
    Index of the performer among the detected people: the largest box.
    None if nobody was detected. bboxes are (N, 4) x1, y1, x2, y2 pixels.
    """
    if len(bboxes) == 0:
        return None
    areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
    return int(np.argmax(areas))


# rtmlib's model pairs for BodyWithFeet, fastest first (config.RTMPOSE_MODE)
RTMPOSE_MODES = ("lightweight", "balanced", "performance")
# where RTMPose runs: the processor, or an NVIDIA GPU through onnxruntime-gpu
RTMPOSE_DEVICES = ("cpu", "cuda")
_ORT_PROVIDER = {"cpu": "CPUExecutionProvider", "cuda": "CUDAExecutionProvider"}


def _preload_cuda_libraries() -> None:
    """
    Make the CUDA and cuDNN libraries findable before ONNX Runtime starts the
    GPU. onnxruntime-gpu installed with its [cuda,cudnn] extras ships them as
    pip packages (nvidia-*), which Windows does not search on its own;
    onnxruntime.preload_dlls() loads them from there, or from a matching
    PyTorch or the system's CUDA install. Older ONNX Runtimes lack it, and a
    failure here is left for the provider check to report.
    """
    import onnxruntime

    preload = getattr(onnxruntime, "preload_dlls", None)
    if preload is not None:
        try:
            preload()
        except Exception:
            pass


def check_rtmpose_device(device: str) -> None:
    """
    Raise RuntimeError, with what to do, if RTMPose cannot run on `device`.
    For "cuda" that means onnxruntime-gpu is installed (not plain
    onnxruntime; the two cannot share a venv) and offers the CUDA provider.
    Called before any video is read, so a GPU run fails in seconds.
    """
    if device not in RTMPOSE_DEVICES:
        raise ValueError(f"RTMPose device must be one of {RTMPOSE_DEVICES}, got {device!r}")
    if device == "cpu":
        return
    import onnxruntime

    _preload_cuda_libraries()
    available = onnxruntime.get_available_providers()
    if _ORT_PROVIDER[device] not in available:
        raise RuntimeError(
            f"RTMPose on the GPU needs onnxruntime-gpu and an NVIDIA GPU; this ONNX Runtime offers "
            f"{', '.join(available)}. Swap the package with: pip uninstall onnxruntime, then "
            f"pip install \"onnxruntime-gpu[cuda,cudnn]\" (same version). Or run with --rtmpose-device cpu.")


class RTMPoseBackend(PoseBackend):
    """
    RTMPose with the Halpe-26 (body with feet) model, through rtmlib
    (github.com/Tau-J/rtmlib, Apache-2.0) on ONNX Runtime.

    A person detector (YOLOX) finds the people, the largest one is taken as
    the performer (pick_person) and RTMPose finds that person's 26 joints.
    With detect_every=1 (the default) the detector runs on every frame; with
    detect_every=N it runs on every Nth frame, and the frames between reuse a
    box around the previous frame's joints (box_from_joints), which skips most
    of the detector's cost. A frame whose joints are too uncertain to box
    sends the next frame back to the detector. rtmlib downloads
    both models on first use (into ~/.cache), so model_path is not used.

    mode: rtmlib's "lightweight", "balanced" or "performance" (slower, more
    accurate). device: "cpu" or "cuda" (needs onnxruntime-gpu). ONNX Runtime
    quietly falls back to the CPU when it cannot start the GPU (missing CUDA
    libraries, for one), so after loading, both models are checked to really
    be on the device asked for.
    """
    name = "rtmpose"
    # Halpe-26 has no eye corners, mouth corners or finger points
    joints = None   # set below, once MEDIAPIPE_FROM_HALPE26 is defined
    # class-level defaults so a backend built without __init__ (the tests) behaves as before
    _detect_every = 1
    _frame = 0
    _box = None

    def __init__(self, model_path: str | None = None, mode: str = config.RTMPOSE_MODE, device: str = "cpu",
                 detect_every: int = config.RTMPOSE_DETECT_EVERY):
        if not isinstance(detect_every, (int, np.integer)) or detect_every < 1:
            raise ValueError(f"detect_every must be a whole number of frames, 1 or more, got {detect_every!r}")
        self._detect_every = int(detect_every)
        if mode not in RTMPOSE_MODES:
            raise ValueError(f"RTMPose mode must be one of {RTMPOSE_MODES}, got {mode!r}")
        check_rtmpose_device(device)

        from rtmlib import BodyWithFeet

        self._model = BodyWithFeet(mode=mode, backend="onnxruntime", device=device)
        self._check_running_on(device)

    def _check_running_on(self, device: str) -> None:
        """RuntimeError if either model ended up somewhere other than `device` (ONNX Runtime's silent fallback)."""
        wanted = _ORT_PROVIDER[device]
        for name, part in (("person detector", self._model.det_model), ("pose model", self._model.pose_model)):
            providers = part.session.get_providers()
            if not providers or providers[0] != wanted:
                raise RuntimeError(
                    f"RTMPose's {name} is running on {providers[0] if providers else 'nothing'}, not "
                    f"{wanted}: ONNX Runtime could not start the GPU. Install onnxruntime-gpu with its CUDA "
                    f"libraries (pip install \"onnxruntime-gpu[cuda,cudnn]\") and check that the NVIDIA "
                    f"driver supports that CUDA version (nvidia-smi), or run with --rtmpose-device cpu.")

    def detect(self, rgb, frame_ms):
        import cv2

        # rtmlib is written for OpenCV's BGR frames (its examples feed cap.read() directly)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # between detector frames, look where the performer was a frame ago
        box = self._box if self._frame % self._detect_every != 0 else None
        self._frame += 1

        if box is None:
            bboxes = np.asarray(self._model.det_model(bgr)).reshape(-1, 4)
            person = pick_person(bboxes)
            if person is None:
                # without a box rtmlib would run the pose model on the whole image
                # and always "find" someone, so no detection means no person
                self._box = None
                return empty_frame()
            box = bboxes[person]

        keypoints, scores = self._model.pose_model(bgr, bboxes=[box])
        if self._detect_every > 1:
            self._box = box_from_joints(keypoints[0], scores[0], bgr.shape[1], bgr.shape[0])
        return halpe26_to_mediapipe(keypoints[0], scores[0])


# Detector name (what run_pipeline's --detector will take) -> backend class.
BACKENDS: dict[str, type[PoseBackend]] = {
    MediaPipeBackend.name: MediaPipeBackend,
    RTMPoseBackend.name: RTMPoseBackend,
}


RTMPoseBackend.joints = tuple(j for j in MEDIAPIPE_JOINTS if j in MEDIAPIPE_FROM_HALPE26)


def joints_provided(name: str = DEFAULT_BACKEND) -> list[str]:
    """The joints detector `name` can find, in MediaPipe order (all 33 for MediaPipe)."""
    joints = BACKENDS[name].joints
    return list(MEDIAPIPE_JOINTS) if joints is None else [j for j in MEDIAPIPE_JOINTS if j in joints]


def create_backend(name: str = DEFAULT_BACKEND, model_path: str | None = None, **options) -> PoseBackend:
    """
    Build the backend registered under name. model_path is ignored by models
    that bring their own. options go to the backend's constructor (RTMPose:
    mode, device, detect_every); see detector_options() in run_pipeline.py.
    """
    try:
        backend_class = BACKENDS[name]
    except KeyError:
        raise ValueError(f"Unknown pose detector {name!r}, choose from: {', '.join(BACKENDS)}") from None
    return backend_class(model_path=model_path, **options)
