"""mocap_pipeline.report: the per-frame numbers behind the desktop tester's result panel."""
import json

import numpy as np

from mocap_pipeline import config, io, report
from mocap_pipeline.joints import JOINT_INDEX, NUM_JOINTS
from mocap_pipeline.schemas import Keypoints2D, Pose3D, SyncResult

from .conftest import make_rig

FRAMES = 20
CLAPS = {"cam0": 0.5, "cam1": 1.0, "cam2": 0.25}


def project(cam, X):
    Xc = X @ cam.R.T + cam.t
    return (Xc @ cam.K.T)[..., :2] / Xc[..., 2:3], Xc[..., 2]


def write_run(tmp_path, shift_px=0.0, lose=None):
    """A run's files for 3 cameras seeing a still cloud of points; cam2's 2D is shifted by shift_px."""
    rig = make_rig(("cam0", "cam1", "cam2"))
    rng = np.random.default_rng(3)
    X = np.repeat(rng.uniform(-0.5, 0.5, size=(1, NUM_JOINTS, 3)), FRAMES, axis=0)
    X[:, JOINT_INDEX["LEFT_PINKY"]] = np.nan               # never triangulated
    out = tmp_path / "out3d.json"
    common = np.arange(FRAMES) / config.TARGET_FPS
    for cam in rig.cameras:
        # each video at 30 fps, starting so its clap lands on the shared clock's zero
        uv, _ = project(cam, np.nan_to_num(X))
        if cam.camera_id == "cam2":
            uv = uv + np.array([shift_px, 0.0])
        conf = np.ones((FRAMES, NUM_JOINTS))
        conf[:, JOINT_INDEX["LEFT_PINKY"]] = 0.0            # no camera reports it
        if lose is not None and cam.camera_id == "cam0":
            conf[lose] = 0.0                                # cam0 loses the performer in these frames
        io.save_keypoints(Keypoints2D(
            camera_id=cam.camera_id, video_path=f"{cam.camera_id}.mp4", width=1920, height=1080,
            fps=30.0, timestamps=common + CLAPS[cam.camera_id], points=uv, confidence=conf),
            str(tmp_path / f"out3d.keypoints.{cam.camera_id}.npz"), fingerprint={})
    io.save_sync(SyncResult(clap_time_s=CLAPS, common_timestamps=common), str(tmp_path / "out3d.sync.json"))
    io.save_rig(rig, str(tmp_path / "calibration.json"))
    views = np.where(np.isfinite(X[..., 0]), 3, 0)
    io.save_pose3d(Pose3D(fps=30.0, points=X, num_views=views), str(tmp_path / "out3d.pose.npz"))
    return out, rig, X


def test_exact_detections_have_no_error_and_cameras_sit_where_the_rig_says(tmp_path):
    out, rig, _ = write_run(tmp_path)
    r = report.build(out)
    assert len(r["times"]) == FRAMES
    assert "LEFT_PINKY" not in r["joints"] and "NOSE" in r["joints"]
    for cam, c in zip(rig.cameras, r["cameras"]):
        np.testing.assert_allclose(c["position"], -cam.R.T @ cam.t, atol=1e-3)
        assert c["calibration_error_px"] == 1.5
    for c in r["per_camera"]:
        assert c["mean_error_px"] < 0.01
        assert c["lost_fraction"] == 0
        assert all(n == len(r["joints"]) for n in c["seen"])


def test_a_shifted_camera_shows_its_shift_in_pixels_and_millimetres(tmp_path):
    out, rig, X = write_run(tmp_path, shift_px=4.0)
    r = report.build(out)
    cam2 = r["per_camera"][2]
    assert abs(cam2["mean_error_px"] - 4.0) < 0.05
    # millimetres at the performer: pixels x distance / focal length
    _, z = project(rig.cameras[2], np.nan_to_num(X))
    j = [JOINT_INDEX[n] for n in r["joints"]]
    expected_mm = float(np.mean(4.0 * z[0, j] / 1000.0 * 1000.0))
    assert abs(cam2["mean_error_mm"] - expected_mm) < 0.5
    assert r["per_camera"][0]["mean_error_px"] < 0.01


def test_frames_where_a_camera_lost_the_performer_are_counted(tmp_path):
    out, _, _ = write_run(tmp_path, lose=slice(5, 10))
    r = report.build(out)
    cam0 = r["per_camera"][0]
    assert cam0["seen"][5:10] == [0] * 5 and cam0["seen"][0] == len(r["joints"])
    assert cam0["lost_fraction"] == 5 / FRAMES
    assert cam0["error_px"][6] is None
    assert cam0["points"][6][0] == [None, None]


def test_write_puts_the_report_next_to_the_output(tmp_path):
    out, _, _ = write_run(tmp_path)
    path = report.write(out)
    assert path == tmp_path / "out3d.report.json"
    assert json.loads(path.read_text())["version"] == report.VERSION


def test_joint_speed_comes_from_the_smoothed_output(tmp_path):
    out, _, X = write_run(tmp_path)
    # the final joints move 0.1 m per frame along x: 3 m/s at 30 fps
    moving = X.copy()
    moving[..., 0] += np.arange(FRAMES)[:, None] * 0.1
    io.save_pose3d_json(Pose3D(fps=30.0, points=moving, num_views=np.ones(X.shape[:2], int)), str(out))
    r = report.build(out)
    speed = np.array(r["joint_speed"], dtype=float)
    assert speed.shape == (FRAMES, len(r["joints"]))
    np.testing.assert_allclose(speed[1:-1], 3.0, atol=0.01)


def test_without_the_output_json_speed_falls_back_to_the_raw_joints(tmp_path):
    out, _, _ = write_run(tmp_path)
    r = report.build(out)
    assert np.allclose(np.array(r["joint_speed"], dtype=float), 0.0)
