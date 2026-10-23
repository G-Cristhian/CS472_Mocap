"""
Stage 1 pose backends: the Halpe-26 -> MediaPipe joint mapping, picking the
performer, and the RTMPose backend's frame handling with a fake model in
place of rtmlib (no model download needed).
"""
import numpy as np
import pytest

from mocap_pipeline.joints import JOINT_INDEX, NUM_JOINTS
from mocap_pipeline.stage1_keypoints import backends
from mocap_pipeline.stage1_keypoints.backends import (HALPE26_JOINTS, MEDIAPIPE_FROM_HALPE26, RTMPoseBackend,
                                                      halpe26_to_mediapipe, pick_person)


def halpe_person(offset=0.0):
    """26 joints with distinct, recognisable coordinates: joint i at (i, 100 + i)."""
    keypoints = np.stack([np.arange(26), 100 + np.arange(26)], axis=1).astype(float) + offset
    scores = np.full(26, 0.9)
    return keypoints, scores


def test_mapping_puts_each_halpe_joint_in_its_mediapipe_slot():
    keypoints, scores = halpe_person()
    points, confidence = halpe26_to_mediapipe(keypoints, scores)

    assert points.shape == (NUM_JOINTS, 2) and confidence.shape == (NUM_JOINTS,)
    for mp_name, halpe_name in MEDIAPIPE_FROM_HALPE26.items():
        np.testing.assert_array_equal(points[JOINT_INDEX[mp_name]], keypoints[HALPE26_JOINTS.index(halpe_name)])
        assert confidence[JOINT_INDEX[mp_name]] == pytest.approx(0.9)


def test_mapping_keeps_left_and_right():
    keypoints, scores = halpe_person()
    points, _ = halpe26_to_mediapipe(keypoints, scores)
    assert points[JOINT_INDEX["LEFT_HEEL"], 0] == HALPE26_JOINTS.index("left_heel")
    assert points[JOINT_INDEX["RIGHT_FOOT_INDEX"], 0] == HALPE26_JOINTS.index("right_big_toe")


def test_joints_halpe_lacks_are_missing():
    points, confidence = halpe26_to_mediapipe(*halpe_person())
    for name in ("LEFT_EYE_INNER", "MOUTH_LEFT", "LEFT_PINKY", "RIGHT_THUMB"):
        assert np.isnan(points[JOINT_INDEX[name]]).all()
        assert confidence[JOINT_INDEX[name]] == 0


def test_every_joint_stages_2_and_3_use_is_filled():
    # calibration joints, plus ears, heels and foot tips (scale_floor) and the rig's sources
    needed = ["LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST",
              "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
              "LEFT_EAR", "RIGHT_EAR", "LEFT_HEEL", "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX"]
    assert set(needed) <= set(MEDIAPIPE_FROM_HALPE26)


def test_scores_are_clipped_and_zero_score_joints_are_nan():
    keypoints, scores = halpe_person()
    scores[HALPE26_JOINTS.index("left_knee")] = 1.7
    scores[HALPE26_JOINTS.index("right_knee")] = 0.0
    points, confidence = halpe26_to_mediapipe(keypoints, scores)

    assert confidence[JOINT_INDEX["LEFT_KNEE"]] == 1.0
    assert confidence[JOINT_INDEX["RIGHT_KNEE"]] == 0.0
    assert np.isnan(points[JOINT_INDEX["RIGHT_KNEE"]]).all()


def test_pick_person_takes_the_largest_box():
    bboxes = np.array([[0, 0, 10, 10], [50, 50, 150, 300], [0, 0, 40, 40]], dtype=float)
    assert pick_person(bboxes) == 1
    assert pick_person(np.zeros((0, 4))) is None


class FakeRtmlib:
    """Stands in for rtmlib.BodyWithFeet: fixed boxes, records which box was posed."""

    def __init__(self, bboxes):
        self.bboxes = np.asarray(bboxes, dtype=float).reshape(-1, 4)
        self.posed = []
        self.detections = 0

    def det_model(self, image):
        self.detections += 1
        return self.bboxes

    def pose_model(self, image, bboxes):
        self.posed.append(np.asarray(bboxes[0]))
        keypoints, scores = halpe_person(offset=bboxes[0][0])
        return keypoints[None], scores[None]


def make_backend(fake):
    backend = RTMPoseBackend.__new__(RTMPoseBackend)   # skip __init__: no rtmlib, no download
    backend._model = fake
    return backend


def test_no_person_gives_an_empty_frame():
    fake = FakeRtmlib([])
    points, confidence = make_backend(fake).detect(np.zeros((480, 640, 3), np.uint8), 0.0)
    assert np.isnan(points).all() and (confidence == 0).all()
    assert fake.posed == []                          # pose model never run on the whole image


def test_detect_poses_only_the_performer():
    fake = FakeRtmlib([[0, 0, 10, 10], [200, 50, 400, 450]])
    points, confidence = make_backend(fake).detect(np.zeros((480, 640, 3), np.uint8), 0.0)

    np.testing.assert_array_equal(fake.posed[0], [200, 50, 400, 450])
    assert points[JOINT_INDEX["NOSE"], 0] == 200      # offset by the chosen box
    assert confidence[JOINT_INDEX["NOSE"]] == pytest.approx(0.9)


def test_both_detectors_are_registered():
    assert {"mediapipe", "rtmpose"} <= set(backends.BACKENDS)
    with pytest.raises(ValueError, match="Unknown pose detector"):
        backends.create_backend("openpose")


def test_unknown_rtmpose_mode_is_rejected_before_loading_rtmlib():
    with pytest.raises(ValueError, match="RTMPose mode must be one of"):
        RTMPoseBackend(mode="turbo")


def test_create_backend_passes_options(monkeypatch):
    seen = {}

    class Recorder(backends.PoseBackend):
        def __init__(self, model_path=None, **options):
            seen.update(options, model_path=model_path)

    monkeypatch.setitem(backends.BACKENDS, "recorder", Recorder)
    backends.create_backend("recorder", "m.task", mode="lightweight")
    assert seen == {"mode": "lightweight", "model_path": "m.task"}


def test_gpu_check_explains_a_cpu_only_onnxruntime(monkeypatch):
    onnxruntime = pytest.importorskip("onnxruntime")
    monkeypatch.setattr(onnxruntime, "get_available_providers", lambda: ["CPUExecutionProvider"])
    with pytest.raises(RuntimeError, match="pip install onnxruntime-gpu"):
        backends.check_rtmpose_device("cuda")
    backends.check_rtmpose_device("cpu")                # always fine
    with pytest.raises(ValueError, match="device must be one of"):
        backends.check_rtmpose_device("tpu")


class FakeSession:
    def __init__(self, providers):
        self.providers = providers

    def get_providers(self):
        return self.providers


def test_silent_cpu_fallback_is_caught():
    fake = FakeRtmlib([])
    fake.det_model = type("Det", (), {"session": FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])})()
    fake.pose_model = type("Pose", (), {"session": FakeSession(["CPUExecutionProvider"])})()
    backend = make_backend(fake)
    with pytest.raises(RuntimeError, match="pose model is running on CPUExecutionProvider"):
        backend._check_running_on("cuda")
    fake.pose_model.session.providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    backend._check_running_on("cuda")                    # both on the GPU: fine


def tracking_backend(fake, every):
    backend = make_backend(fake)
    backend._detect_every = every
    return backend


def test_detect_every_n_runs_the_detector_on_every_nth_frame():
    fake = FakeRtmlib([[200, 50, 400, 450]])
    backend = tracking_backend(fake, 3)
    frame = np.zeros((480, 640, 3), np.uint8)
    for i in range(7):
        backend.detect(frame, i * 33.0)
    assert fake.detections == 3                          # frames 0, 3 and 6
    # in between, the box comes from the previous frame's joints, not the detector
    joints = halpe_person(offset=200)[0]
    assert fake.posed[1][0] < joints[:, 0].min() and fake.posed[1][2] > joints[:, 0].max()


def test_every_frame_is_the_default():
    fake = FakeRtmlib([[200, 50, 400, 450]])
    backend = make_backend(fake)
    for i in range(4):
        backend.detect(np.zeros((480, 640, 3), np.uint8), i * 33.0)
    assert fake.detections == 4


def test_uncertain_joints_send_the_next_frame_to_the_detector():
    class Unsure(FakeRtmlib):
        def pose_model(self, image, bboxes):
            keypoints, scores = super().pose_model(image, bboxes)
            return keypoints, scores * 0.1                # every joint below the tracking score
    fake = Unsure([[200, 50, 400, 450]])
    backend = tracking_backend(fake, 10)
    for i in range(3):
        backend.detect(np.zeros((480, 640, 3), np.uint8), i * 33.0)
    assert fake.detections == 3


def test_box_from_joints_stays_in_the_image():
    keypoints = np.array([[-20.0, 10], [630, 470], [300, 200], [310, 210], [320, 220], [330, 230]])
    box = backends.box_from_joints(keypoints, np.full(6, 0.9), 640, 480)
    assert box[0] == 0 and box[1] == 0 and box[2] == 639 and box[3] == 479
    assert backends.box_from_joints(keypoints[:3], np.full(3, 0.9), 640, 480) is None   # too few joints


def test_detect_every_is_validated():
    with pytest.raises(ValueError, match="detect_every must be a whole number"):
        RTMPoseBackend(detect_every=0)
