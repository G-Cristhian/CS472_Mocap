"""
Stage 1 run several videos at a time (run_pipeline._detect_videos) and the
report of which videos failed. The parallel path really spawns processes, so
the stand-in worker is a module-level function the child can import.
"""
import sys
from pathlib import Path

import pytest

from mocap_pipeline import config, io, metrics, run_pipeline
from mocap_pipeline.stage1_keypoints import detect
from tests.conftest import make_keypoints


def fake_worker(video, model_path, detector, kp_path, fingerprint, camera_id, queue):
    """Stands in for _detect_worker in a child process: prints like detect.py, saves a joints file, fails on 'bad'."""
    writer = run_pipeline._QueueWriter(queue, camera_id)
    sys.stdout = writer
    try:
        for f in (30, 60):
            print(f"progress: detect {video} {f}/60")
        if Path(video).name.startswith("bad"):
            raise ValueError(f"No frames could be read from video: {video}")
        io.save_keypoints(make_keypoints(camera_id=camera_id, video_path=video), kp_path, fingerprint)
        return camera_id, 0.25
    finally:
        writer.close()
        sys.stdout = sys.__stdout__


def todo_for(tmp_path, names):
    out = []
    for name in names:
        video = tmp_path / name
        video.write_bytes(b"stand-in")
        cid = video.stem
        out.append((str(video), cid, tmp_path / f"out3d.keypoints.{cid}.npz", {"detector": "mediapipe"}))
    return out


def test_detect_jobs_auto_and_explicit(monkeypatch):
    monkeypatch.setattr(config, "DETECT_MAX_AUTO_JOBS", 4)
    monkeypatch.setattr(run_pipeline.os, "cpu_count", lambda: 8)
    assert run_pipeline.detect_jobs(3, 0) == 3            # one per video
    assert run_pipeline.detect_jobs(6, 0) == 4            # capped by the auto limit
    monkeypatch.setattr(run_pipeline.os, "cpu_count", lambda: 2)
    assert run_pipeline.detect_jobs(6, 0) == 2            # capped by the cores
    assert run_pipeline.detect_jobs(6, 3) == 3            # explicit
    assert run_pipeline.detect_jobs(2, 3) == 2            # never more than the videos
    with pytest.raises(ValueError, match="jobs"):
        run_pipeline.detect_jobs(2, -1)


def test_videos_are_detected_in_parallel_and_their_lines_relayed(tmp_path, capsys):
    todo = todo_for(tmp_path, ["cam0.mp4", "cam1.mp4", "cam2.mp4"])
    seconds, failures = run_pipeline._detect_videos(todo, "unused", "mediapipe", 3, worker=fake_worker)
    assert failures == {}
    assert set(seconds) == {"cam0", "cam1", "cam2"}
    for _, cid, kp_path, _ in todo:
        assert io.load_keypoints(str(kp_path)).camera_id == cid
    out = capsys.readouterr().out
    for _, cid, _, _ in todo:
        assert f"progress: detect {tmp_path / cid}.mp4 60/60" in out    # the child's prints reached this process
        assert f"Detected joints in {tmp_path / cid}.mp4" in out


def test_one_bad_video_does_not_stop_the_others(tmp_path, capsys):
    todo = todo_for(tmp_path, ["cam0.mp4", "bad.mp4", "cam2.mp4"])
    seconds, failures = run_pipeline._detect_videos(todo, "unused", "mediapipe", 2, worker=fake_worker)
    assert set(seconds) == {"cam0", "cam2"}
    assert list(failures) == ["bad"] and failures["bad"].startswith("ValueError: No frames could be read")
    assert (tmp_path / "out3d.keypoints.cam0.npz").exists() and (tmp_path / "out3d.keypoints.cam2.npz").exists()
    assert not (tmp_path / "out3d.keypoints.bad.npz").exists()
    assert "Detection failed for" in capsys.readouterr().out


def test_run_reports_every_failed_file_and_keeps_the_good_ones(tmp_path, monkeypatch):
    def fake_detect(video_path, model_path, detector="mediapipe"):
        if "bad" in str(video_path):
            raise RuntimeError("cannot decode")
        return make_keypoints(camera_id=Path(video_path).stem, video_path=video_path)

    monkeypatch.setattr(detect, "detect_video", fake_detect)
    videos = []
    for name in ("cam0.mp4", "bad1.mp4", "bad2.mp4"):
        (tmp_path / name).write_bytes(b"x")
        videos.append(str(tmp_path / name))
    out = tmp_path / "output" / "out3d.json"

    with pytest.raises(SystemExit) as info:
        run_pipeline.run(videos, str(out), model_path="unused", jobs=1)

    message = str(info.value)
    assert "Detection failed for bad1.mp4: RuntimeError: cannot decode" in message
    assert "Detection failed for bad2.mp4: RuntimeError: cannot decode" in message
    assert message.splitlines()[-1].startswith("Detection failed for 2 of 3 video(s): bad1.mp4, bad2.mp4")
    assert "--resume" in message
    assert (out.parent / "out3d.keypoints.cam0.npz").exists()      # the good one is saved for --resume
    m = metrics.load(str(out))
    assert m["run"]["status"] == "failed" and set(m["stage1"]["failed"]) == {"bad1", "bad2"}
