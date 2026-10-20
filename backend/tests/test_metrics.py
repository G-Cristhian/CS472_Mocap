"""
metrics.py: recording, the per-stage summaries, and the files run_pipeline
writes. The end-to-end case runs the real stages 2 and 3 on the synthetic
scene and checks that the numbers say what a good run should say.
"""
import json

import numpy as np
import pytest

from mocap_pipeline import config, io, metrics, run_pipeline
from mocap_pipeline.joints import JOINT_INDEX, RIG_JOINTS, RIG_PARENTS
from mocap_pipeline.stage1_keypoints import detect
from mocap_pipeline.stage3_rig import skeleton
from tests.conftest import make_keypoints
from tests.synthetic_scene import PERFORMER_HEIGHT_M, Noise, Routine, Scene

SHORT = Routine(stand_s=2.0, walk_s=6.0, perform_s=3.0)
REALISTIC = Noise(pixel_sigma=1.5, dropout=0.02, outlier=0.005)


# ---- recording ---------------------------------------------------------------

def test_record_is_a_no_op_outside_a_run():
    metrics.record("x.y", 1)
    assert not metrics.active()


def test_record_nests_dotted_keys_and_cleans_numpy(tmp_path):
    out = tmp_path / "o.json"
    metrics.start(str(out), detector="mediapipe")
    try:
        metrics.record("a.b.c", np.float32(1.5))
        metrics.record("a.b.d", {"n": np.int64(3), "nan": np.nan, "arr": np.array([1, 2])})
        with metrics.time("fast"):
            pass
        assert metrics.active()
    finally:
        path = metrics.finish("done")
    data = json.loads(path.read_text())
    assert data["a"]["b"] == {"c": 1.5, "d": {"n": 3, "nan": None, "arr": [1, 2]}}
    assert data["run"]["detector"] == "mediapipe" and data["run"]["status"] == "done"
    assert data["timing"]["fast_s"] >= 0
    assert not metrics.active()
    assert io.stage_paths(str(out))["metrics"] == path


def test_log_file_copies_stdout(tmp_path, capsys):
    out = tmp_path / "o.json"
    metrics.start(str(out))
    try:
        print("hello from the run")
    finally:
        metrics.finish()
    assert "hello from the run" in capsys.readouterr().out            # still printed
    assert "hello from the run" in (tmp_path / "o.log").read_text()  # and logged


# ---- summaries -----------------------------------------------------------------

def test_keypoints_summary():
    kp = make_keypoints(frames=12)
    kp.confidence[0] = 0.0                                             # one frame with no person
    s = metrics.keypoints_summary(kp)
    assert s["frames"] == 12 and s["no_person_fraction"] == pytest.approx(1 / 12)
    assert 0 < s["mean_confidence"] <= 1
    assert set(s["mean_confidence_per_joint"]) == set(JOINT_INDEX)


def test_pose_summary_leaves_out_joints_the_detector_does_not_have():
    pose = Scene(routine=SHORT).truth_pose()            # MediaPipe-style: no extra joints
    pose.points[:10, JOINT_INDEX["NOSE"]] = np.nan
    detected = np.isfinite(pose.points).all(axis=2).any(axis=0)
    s = metrics.pose_summary(pose, detected)
    assert s["missing_fraction_per_joint"]["HEAD_TOP"] is None
    assert s["missing_fraction_per_joint"]["NOSE"] == pytest.approx(10 / len(pose.points))
    assert s["missing_fraction"] == pytest.approx(10 / len(pose.points) / 33)
    assert metrics.pose_summary(pose)["missing_fraction_per_joint"]["HEAD_TOP"] == 1.0   # without detected


def test_detected_joints_are_the_ones_any_camera_saw():
    a, b = make_keypoints(camera_id="cam0"), make_keypoints(camera_id="cam1")
    a.points[:, JOINT_INDEX["HEAD_TOP"]] = np.nan
    b.points[:, JOINT_INDEX["HEAD_TOP"]] = np.nan
    a.points[:, JOINT_INDEX["NECK"]] = np.nan          # cam1 still has it
    detected = metrics.detected_joints([a, b])
    assert not detected[JOINT_INDEX["HEAD_TOP"]] and detected[JOINT_INDEX["NECK"]]
    assert detected.sum() == len(detected) - 1


def test_bone_length_summary_is_zero_on_the_rigid_synthetic_performer():
    rig = skeleton.rig_joint_positions(Scene(routine=SHORT).truth_pose())
    s = metrics.bone_length_summary(rig, RIG_JOINTS, RIG_PARENTS)
    assert s["max_std_m"] < 1e-6
    assert s["per_bone"]["LeftKnee"]["median_m"] == pytest.approx(0.42, abs=1e-6)


# ---- the files a run writes ---------------------------------------------------------

def run_synthetic(tmp_path, monkeypatch, extra_joints=False, **kw):
    scene = Scene(routine=SHORT, fps=(60.0, 30.0, 30.0), clap_s=(1.0, 0.85, 2.3), noise=REALISTIC,
                  extra_joints=extra_joints)
    recorded = {k.video_path: k for k in scene.recorded_keypoints(str(tmp_path))}
    for path in recorded:
        (tmp_path / path.split("/")[-1]).write_bytes(b"stand-in for a phone video")
    monkeypatch.setattr(detect, "detect_video",
                        lambda video_path, model_path, detector="mediapipe": recorded[str(video_path)])
    out = tmp_path / "output" / "take.json"
    kw.setdefault("jobs", 1)    # the fake detector lives in this process
    run_pipeline.run(list(recorded), str(out), performer_height_m=PERFORMER_HEIGHT_M, model_path="unused",
                     camera=["webcam"] * 3, fov=[65.0] * 3, clap_times=scene.clap_times(),
                     calibration_path=str(tmp_path / "output" / "calibration.json"), **kw)
    return out


def test_run_writes_metrics_that_describe_a_good_take(tmp_path, monkeypatch):
    out = run_synthetic(tmp_path, monkeypatch)
    m = metrics.load(str(out))

    assert m["run"]["status"] == "done" and m["run"]["detector"] == "mediapipe"
    assert {"sync", "calibrate", "triangulate", "smooth", "rig", "total"} <= {k[:-2] for k in m["timing"]}
    assert set(m["stage1"]) == {"cam0", "cam1", "cam2"}
    assert m["sync"]["clap_times_from"] == "given" and m["sync"]["common_fps"] == config.TARGET_FPS
    assert m["calibrate"]["start_pair"] and len(m["calibrate"]["distinct_correspondences"]) == 3
    assert max(m["calibrate"]["reprojection_error_px"].values()) < 3.0
    assert m["calibrate"]["from_board"] is False
    assert m["scale"]["upright_frames"] >= config.MIN_UPRIGHT_FRAMES
    assert m["scale"]["height_from"] == "ears"                  # MediaPipe-style joints: no head top
    assert m["floor"]["plane_used"] is True and m["floor"]["tilt_from_body_up_deg"] < 2.0
    assert m["triangulate"]["mean_reprojection_px"] < 3.0
    assert set(m["triangulate"]["mean_reprojection_px_per_joint"]) == set(JOINT_INDEX)
    assert m["pose_final"]["missing_fraction"] <= m["pose_raw"]["missing_fraction"]
    assert m["pose_final"]["missing_fraction"] < 0.05
    assert m["pose_final"]["missing_fraction_per_joint"]["HEAD_TOP"] is None     # not counted as missing
    assert m["triangulate"]["mean_reprojection_px_per_joint"]["HEAD_TOP"] is None
    assert m["triangulate"]["joints_with_fewer_than_2_views"] < 0.05 * m["triangulate"]["frames"] * 33
    assert m["rig"]["detected_fraction"]["Head"] == 0.0
    assert m["rig"]["bone_lengths"]["mean_std_m"] < 0.02       # realistic noise at 4 m: a few mm
    assert m["smooth"]["gaps"]["filled"] >= 0

    log = (out.parent / "take.log").read_text()
    assert "Saved" in log and "frames of 3D joints" in log


def test_run_with_the_head_top_measures_the_height_to_it(tmp_path, monkeypatch):
    out = run_synthetic(tmp_path, monkeypatch, extra_joints=True)
    m = metrics.load(str(out))
    assert m["scale"]["height_from"] == "head top"
    assert m["scale"]["upright_frames_with_head_top"] >= config.MIN_UPRIGHT_FRAMES
    # the scene puts the head top exactly HEAD_TOP_ABOVE_EARS_M above the ears, so both rules agree
    assert m["scale"]["height_to_head_top_m"] == pytest.approx(PERFORMER_HEIGHT_M, abs=1e-9)
    assert m["scale"]["height_to_ears_m"] == pytest.approx(PERFORMER_HEIGHT_M, abs=0.015)
    assert m["scale"]["head_top_above_ears_m"] == pytest.approx(config.HEAD_TOP_ABOVE_EARS_M, abs=0.015)
    assert m["rig"]["detected_fraction"]["Head"] > 0.95
    assert m["pose_final"]["missing_fraction_per_joint"]["HEAD_TOP"] < 0.05


def test_failed_run_still_writes_metrics(tmp_path, monkeypatch):
    def boom(video_path, model_path, detector="mediapipe"):
        raise RuntimeError("detector exploded")
    monkeypatch.setattr(detect, "detect_video", boom)
    for name in ("cam0.mp4", "cam1.mp4"):
        (tmp_path / name).write_bytes(b"x")
    out = tmp_path / "output" / "take.json"
    with pytest.raises(SystemExit, match="cam0.mp4.*detector exploded") as info:
        run_pipeline.run([str(tmp_path / "cam0.mp4"), str(tmp_path / "cam1.mp4")], str(out), model_path="unused",
                         jobs=1)
    assert "2 of 2 video(s): cam0.mp4, cam1.mp4" in str(info.value)
    m = metrics.load(str(out))
    assert m["run"]["status"] == "failed" and "detector exploded" in m["run"]["error"]
    assert set(m["stage1"]["failed"]) == {"cam0", "cam1"}
    assert not metrics.active()


def test_stop_after_records_the_stage(tmp_path, monkeypatch):
    out = run_synthetic(tmp_path, monkeypatch, stop_after="sync")
    m = metrics.load(str(out))
    assert m["run"]["status"] == "stopped after sync"
    assert "sync" in m and "calibrate" not in m
