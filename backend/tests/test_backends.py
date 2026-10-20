"""
Stage 1 pose backends: the Halpe-26 -> joints.JOINTS mapping, picking the
performer, and the RTMPose backend's frame handling with a fake model in
place of rtmlib (no model download needed).
"""
import numpy as np
import pytest

from mocap_pipeline.joints import EXTRA_JOINTS, JOINT_INDEX, MEDIAPIPE_JOINTS, NUM_JOINTS
from mocap_pipeline.stage1_keypoints import backends
from mocap_pipeline.stage1_keypoints.backends import (HALPE26_JOINTS, JOINTS_FROM_HALPE26, RTMPoseBackend,
                                                      halpe26_to_joints, pick_person)


def halpe_person(offset=0.0):
    """26 joints with distinct, recognisable coordinates: joint i at (i, 100 + i)."""
    keypoints = np.stack([np.arange(26), 100 + np.arange(26)], axis=1).astype(float) + offset
    scores = np.full(26, 0.9)
    return keypoints, scores


def test_mapping_puts_each_halpe_joint_in_its_slot():
    keypoints, scores = halpe_person()
    points, confidence = halpe26_to_joints(keypoints, scores)

    assert points.shape == (NUM_JOINTS, 2) and confidence.shape == (NUM_JOINTS,)
    for name, halpe_name in JOINTS_FROM_HALPE26.items():
        np.testing.assert_array_equal(points[JOINT_INDEX[name]], keypoints[HALPE26_JOINTS.index(halpe_name)])
        assert confidence[JOINT_INDEX[name]] == pytest.approx(0.9)


def test_every_halpe_joint_is_kept_and_the_extras_come_after_mediapipes():
    assert sorted(JOINTS_FROM_HALPE26.values()) == sorted(HALPE26_JOINTS)
    assert len(set(JOINTS_FROM_HALPE26.values())) == 26
    points, _ = halpe26_to_joints(*halpe_person())
    for name, halpe_name in [("HEAD_TOP", "head"), ("NECK", "neck"), ("MID_HIP", "hip"),
                             ("LEFT_SMALL_TOE", "left_small_toe"), ("RIGHT_SMALL_TOE", "right_small_toe")]:
        assert points[JOINT_INDEX[name], 0] == HALPE26_JOINTS.index(halpe_name)
    # MediaPipe's indices did not move
    assert [JOINT_INDEX[n] for n in MEDIAPIPE_JOINTS] == list(range(33))
    assert [JOINT_INDEX[n] for n in EXTRA_JOINTS] == list(range(33, NUM_JOINTS))


def test_mapping_keeps_left_and_right():
    keypoints, scores = halpe_person()
    points, _ = halpe26_to_joints(keypoints, scores)
    assert points[JOINT_INDEX["LEFT_HEEL"], 0] == HALPE26_JOINTS.index("left_heel")
    assert points[JOINT_INDEX["RIGHT_FOOT_INDEX"], 0] == HALPE26_JOINTS.index("right_big_toe")


def test_joints_halpe_lacks_are_missing():
    points, confidence = halpe26_to_joints(*halpe_person())
    for name in ("LEFT_EYE_INNER", "MOUTH_LEFT", "LEFT_PINKY", "RIGHT_THUMB"):
        assert np.isnan(points[JOINT_INDEX[name]]).all()
        assert confidence[JOINT_INDEX[name]] == 0


def test_every_joint_stages_2_and_3_use_is_filled():
    # calibration joints, plus ears, heels and foot tips (scale_floor) and the rig's sources
    needed = ["LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST",
              "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
              "LEFT_EAR", "RIGHT_EAR", "LEFT_HEEL", "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX"]
    assert set(needed + ["HEAD_TOP"]) <= set(JOINTS_FROM_HALPE26)


def test_scores_are_clipped_and_zero_score_joints_are_nan():
    keypoints, scores = halpe_person()
    scores[HALPE26_JOINTS.index("left_knee")] = 1.7
    scores[HALPE26_JOINTS.index("right_knee")] = 0.0
    points, confidence = halpe26_to_joints(keypoints, scores)

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

    def det_model(self, image):
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
