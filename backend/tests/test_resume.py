"""
run_pipeline.run() with --resume, --stop-after and --detector, with stage 1,
sync's audio search and triangulation replaced by fakes that count their calls.
Calibration is skipped by pre-writing a calibration.json, as a second run would.
"""
import os
from pathlib import Path

import pytest

from mocap_pipeline import io, run_pipeline
from mocap_pipeline.stage1_keypoints import detect
from mocap_pipeline.stage2_reconstruct import smooth, sync, triangulate
from tests.conftest import make_keypoints, make_pose, make_rig, make_sync


class Calls:
    def __init__(self):
        self.detect = []
        self.detectors = []
        self.sync_clap_times = []
        self.sync_thresholds = []
        self.triangulate = 0


@pytest.fixture
def fakes(monkeypatch, fake_videos):
    calls = Calls()

    def fake_detect(video_path, model_path, detector="mediapipe"):
        calls.detect.append(os.path.basename(video_path))
        calls.detectors.append(detector)
        return make_keypoints(camera_id=Path(video_path).stem, video_path=video_path)

    def fake_synchronise(video_paths, keypoints, clap_times=None, clap_threshold=1.0, signal="clap"):
        calls.sync_clap_times.append(clap_times)
        calls.sync_thresholds.append(clap_threshold)
        if clap_times is None:
            clap_times = [1.0, 1.25]          # "found in the audio"
        ids = [kp.camera_id for kp in keypoints]
        return make_sync(ids), keypoints

    def fake_triangulate(keypoints, rig):
        calls.triangulate += 1
        return make_pose()

    monkeypatch.setattr(detect, "detect_video", fake_detect)
    monkeypatch.setattr(sync, "synchronise", fake_synchronise)
    monkeypatch.setattr(triangulate, "triangulate_sequence", fake_triangulate)
    monkeypatch.setattr(run_pipeline, "camera_types", lambda videos, choices: ["webcam"] * len(videos))
    return calls


def run(fake_videos, tmp_path, **kw):
    out = tmp_path / "output" / "out3d.json"
    calib = tmp_path / "output" / "calibration.json"
    if not calib.exists():
        io.save_rig(make_rig(["cam0", "cam1"]), str(calib))
    kw.setdefault("jobs", 1)    # the fakes patch detect_video in this process
    run_pipeline.run(fake_videos, str(out), model_path="unused.task", calibration_path=str(calib),
                     smoothing=False, bvh=False, **kw)
    return out


def bump_mtime(path, seconds=5):
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns + seconds * 10**9, st.st_mtime_ns + seconds * 10**9))


def test_first_run_writes_every_stage_file(fakes, fake_videos, tmp_path):
    out = run(fake_videos, tmp_path)
    paths = io.stage_paths(str(out), ["cam0", "cam1"])
    assert out.exists()
    assert paths["sync"].exists() and paths["pose"].exists()
    assert all(p.exists() for p in paths["keypoints"].values())
    assert fakes.detect == ["cam0.mp4", "cam1.mp4"]
    assert fakes.triangulate == 1
    assert fakes.sync_clap_times == [None]           # audio search ran


def test_resume_skips_detection_sync_and_triangulation(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path)
    run(fake_videos, tmp_path, resume=True)
    assert fakes.detect == ["cam0.mp4", "cam1.mp4"]  # no new detections
    assert fakes.triangulate == 1
    assert fakes.sync_clap_times[-1] == [1.0, 1.25]  # saved clap times reused


def test_without_resume_everything_reruns(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path)
    run(fake_videos, tmp_path)
    assert fakes.detect == ["cam0.mp4", "cam1.mp4"] * 2
    assert fakes.triangulate == 2


def test_changed_video_is_detected_again(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path)
    bump_mtime(fake_videos[1])
    run(fake_videos, tmp_path, resume=True)
    assert fakes.detect == ["cam0.mp4", "cam1.mp4", "cam1.mp4"]
    assert fakes.triangulate == 2                    # a new keypoints file makes the pose stale


def test_new_calibration_retriangulates(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path)
    bump_mtime(tmp_path / "output" / "calibration.json")
    run(fake_videos, tmp_path, resume=True)
    assert len(fakes.detect) == 2
    assert fakes.triangulate == 2


def test_explicit_sync_overrides_saved(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path)
    run(fake_videos, tmp_path, resume=True, clap_times=[2.0, 2.5])
    assert fakes.sync_clap_times[-1] == [2.0, 2.5]
    assert io.load_sync(str(tmp_path / "output" / "out3d.sync.json")).clap_time_s["cam0"] == 1.0  # fake ignores input, file rewritten


def test_detector_reaches_stage_1(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path, detector="rtmpose")
    assert fakes.detectors == ["rtmpose", "rtmpose"]


def test_switching_detector_detects_again(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path)
    run(fake_videos, tmp_path, resume=True, detector="rtmpose")
    assert fakes.detectors == ["mediapipe"] * 2 + ["rtmpose"] * 2
    assert fakes.triangulate == 2                    # new joints make the pose stale


def test_same_detector_resumes(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path, detector="rtmpose")
    run(fake_videos, tmp_path, resume=True, detector="rtmpose")
    assert fakes.detectors == ["rtmpose"] * 2


def test_saved_joints_without_a_detector_count_as_mediapipe(fakes, fake_videos, tmp_path):
    out = run(fake_videos, tmp_path)
    for cid, kp_path in io.stage_paths(str(out), ["cam0", "cam1"])["keypoints"].items():
        kp = io.load_keypoints(str(kp_path))            # rewrite as saved before --detector existed
        io.save_keypoints(kp, str(kp_path), io.video_fingerprint(str(tmp_path / f"{cid}.mp4")))
    run(fake_videos, tmp_path, resume=True)
    assert len(fakes.detect) == 2                       # still reused
    run(fake_videos, tmp_path, resume=True, detector="rtmpose")
    assert fakes.detectors[-2:] == ["rtmpose", "rtmpose"]


def test_clap_threshold_reaches_the_clap_search(fakes, fake_videos, tmp_path):
    run(fake_videos, tmp_path, clap_threshold=0.5)
    assert fakes.sync_thresholds == [0.5]
    with pytest.raises(ValueError, match="clap_threshold"):
        run(fake_videos, tmp_path, clap_threshold=0)


def test_unknown_detector_is_rejected(fakes, fake_videos, tmp_path):
    with pytest.raises(ValueError, match="detector"):
        run(fake_videos, tmp_path, detector="openpose")


def test_unknown_smoother_is_rejected(fakes, fake_videos, tmp_path):
    with pytest.raises(ValueError, match="smoother"):
        run(fake_videos, tmp_path, smoother="kalman")


def test_smoother_reaches_stage_2c_on_every_run(fakes, fake_videos, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(smooth, "smooth", lambda pose, method=None: seen.append(method) or pose)
    out = tmp_path / "output" / "out3d.json"
    calib = tmp_path / "output" / "calibration.json"
    io.save_rig(make_rig(["cam0", "cam1"]), str(calib))
    for kw in ({}, {"resume": True, "smoother": "butterworth"}, {"resume": True, "smoother": "savgol"}):
        run_pipeline.run(fake_videos, str(out), model_path="unused.task", calibration_path=str(calib),
                         bvh=False, jobs=1, **kw)
    assert seen == ["savgol", "butterworth", "savgol"]   # smoothing reruns under --resume, with the chosen filter
    assert fakes.triangulate == 1                        # on the same triangulation


def test_stop_after_keypoints(fakes, fake_videos, tmp_path):
    out = tmp_path / "output" / "out3d.json"
    run_pipeline.run(fake_videos, str(out), model_path="unused.task", stop_after="keypoints", jobs=1)
    paths = io.stage_paths(str(out), ["cam0", "cam1"])
    assert all(p.exists() for p in paths["keypoints"].values())
    assert not paths["sync"].exists() and not out.exists()
    assert fakes.sync_clap_times == []


def test_stop_after_rejects_unknown_stage(fakes, fake_videos, tmp_path):
    with pytest.raises(ValueError):
        run_pipeline.run(fake_videos, str(tmp_path / "o.json"), stop_after="smooth")


def test_five_videos_run_and_one_is_rejected(fakes, tmp_path):
    """No maximum camera count (D-024); the minimum of 2 stays (D-002)."""
    videos = []
    for c in range(5):
        p = tmp_path / f"cam{c}.mp4"
        p.write_bytes(b"not really a video " + p.name.encode())
        videos.append(str(p))
    calib = tmp_path / "output" / "calibration.json"
    io.save_rig(make_rig([f"cam{c}" for c in range(5)]), str(calib))
    run_pipeline.run(videos, str(tmp_path / "output" / "out3d.json"), model_path="unused.task",
                     calibration_path=str(calib), smoothing=False, bvh=False, jobs=1)
    assert fakes.detect == [f"cam{c}.mp4" for c in range(5)]

    with pytest.raises(ValueError, match="at least 2"):
        run_pipeline.run(videos[:1], str(tmp_path / "output" / "one.json"), model_path="unused.task")


def test_duplicate_video_stems_get_unique_ids(tmp_path):
    a = tmp_path / "a" / "IMG_0001.MOV"
    b = tmp_path / "b" / "IMG_0001.MOV"
    assert run_pipeline.camera_ids_for([str(a), str(b)]) == ["cam0_IMG_0001", "cam1_IMG_0001"]
    assert run_pipeline.camera_ids_for(["x/cam0.mp4", "y/cam1.mp4"]) == ["cam0", "cam1"]
