"""Round trips for every schemas dataclass through io.py, and the video fingerprint."""
import os
import time
from pathlib import Path

import numpy as np

from mocap_pipeline import io
from tests.conftest import make_keypoints, make_pose, make_rig, make_sync


def test_keypoints_round_trip(tmp_path):
    kp = make_keypoints()
    path = tmp_path / "kp.npz"
    io.save_keypoints(kp, str(path), fingerprint={"size": 1, "mtime_ns": 2})

    back, fingerprint = io.load_keypoints(str(path), with_fingerprint=True)

    assert back.camera_id == kp.camera_id
    assert back.video_path == kp.video_path
    assert (back.width, back.height) == (kp.width, kp.height)
    assert back.fps == kp.fps
    np.testing.assert_allclose(back.timestamps, kp.timestamps)
    np.testing.assert_allclose(back.points, kp.points, rtol=1e-6)      # float32 on disk
    np.testing.assert_allclose(back.confidence, kp.confidence, rtol=1e-6)
    assert np.isnan(back.points[3, 5]).all()
    assert fingerprint == {"size": 1, "mtime_ns": 2}
    assert io.load_keypoints(str(path)).camera_id == kp.camera_id   # default returns only the object


def test_sync_round_trip(tmp_path):
    sync = make_sync()
    path = tmp_path / "sync.json"
    io.save_sync(sync, str(path))
    back = io.load_sync(str(path))
    assert back.clap_time_s == sync.clap_time_s
    np.testing.assert_allclose(back.common_timestamps, sync.common_timestamps)


def test_rig_round_trip(tmp_path):
    rig = make_rig()
    path = tmp_path / "rig.json"
    io.save_rig(rig, str(path))
    back = io.load_rig(str(path))
    assert back.is_metric == rig.is_metric
    assert back.reprojection_error_px == rig.reprojection_error_px
    for a, b in zip(back.cameras, rig.cameras):
        assert a.camera_id == b.camera_id
        np.testing.assert_allclose(a.K, b.K)
        np.testing.assert_allclose(a.R, b.R)
        np.testing.assert_allclose(a.t, b.t)


def test_pose3d_round_trip(tmp_path):
    pose = make_pose()
    path = tmp_path / "pose.npz"
    io.save_pose3d(pose, str(path))
    back = io.load_pose3d(str(path))
    assert back.fps == pose.fps
    np.testing.assert_allclose(back.points, pose.points, rtol=1e-6)
    np.testing.assert_array_equal(back.num_views, pose.num_views)
    assert np.isnan(back.points[pose.num_views == 0]).all()


def test_pose3d_json_has_null_for_gaps(tmp_path):
    pose = make_pose()
    path = tmp_path / "out3d.json"
    io.save_pose3d_json(pose, str(path))
    import json
    frames = json.load(open(path))
    assert len(frames) == len(pose.points)
    gap_frame, gap_joint = np.argwhere(pose.num_views == 0)[0]
    name = io.MEDIAPIPE_JOINTS[gap_joint]
    assert frames[gap_frame]["landmarks"][name] is None


def test_stage_paths_follow_out_path():
    paths = io.stage_paths("/x/output/take01.json", ["cam0", "cam1"])
    assert Path(paths["sync"]) == Path("/x/output/take01.sync.json")
    assert Path(paths["pose"]) == Path("/x/output/take01.pose.npz")
    assert Path(paths["keypoints"]["cam1"]) == Path("/x/output/take01.keypoints.cam1.npz")


def test_fingerprint_detects_changed_video(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"abc")
    saved = io.video_fingerprint(str(video))
    assert io.fingerprint_matches(saved, str(video))

    # same size, different mtime
    os.utime(video, ns=(saved["mtime_ns"] + 10**9, saved["mtime_ns"] + 10**9))
    assert not io.fingerprint_matches(saved, str(video))

    # different size
    video.write_bytes(b"abcd")
    assert not io.fingerprint_matches(saved, str(video))

    # missing file or garbage fingerprint never matches
    assert not io.fingerprint_matches(saved, str(tmp_path / "missing.mp4"))
    assert not io.fingerprint_matches({}, str(video))
