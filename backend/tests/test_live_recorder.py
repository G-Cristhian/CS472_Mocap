"""
Tests for backend/live_stream_test/live_recorder.py and recording endpoints in server.py.
Verifies multi-camera live footage recording and mocap_pipeline BVH export.
"""
import os
import json
import time
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from live_stream_test.live_recorder import LiveRecorder, CameraVideoWriter
from live_stream_test import server
from tests.synthetic_scene import pose_at


def test_camera_video_writer(tmp_path):
    video_path = tmp_path / "test_cam.mp4"
    writer = CameraVideoWriter(video_path, fps=30.0, width=320, height=240)

    # Write 15 mock frames
    for _ in range(15):
        frame = np.full((240, 320, 3), 100, dtype=np.uint8)
        writer.write_frame(frame)
    writer.close()

    assert video_path.exists()
    assert writer.frames_written == 15
    assert video_path.stat().st_size > 0


def test_live_recorder_end_to_end(tmp_path):
    recorder = LiveRecorder(base_output_dir=tmp_path / "recordings")

    active_cams = {
        "cam0": {"name": "Camera 0", "source": 0, "width": 320, "height": 240, "fps": 30.0},
        "cam1": {"name": "Camera 1", "source": 1, "width": 320, "height": 240, "fps": 30.0},
    }

    # 1. Start recording
    start_res = recorder.start_recording(take_id="test_take_01", active_cameras=active_cams)
    assert start_res["ok"] is True
    assert recorder.is_recording is True
    assert start_res["take_id"] == "test_take_01"

    take_dir = Path(start_res["take_dir"])
    assert take_dir.exists()

    # 2. Feed simulated frames with 3D pose trajectory
    n_frames = 30
    for f in range(n_frames):
        t = f / 30.0
        frame_cam0 = np.full((240, 320, 3), 50 + f, dtype=np.uint8)
        frame_cam1 = np.full((240, 320, 3), 80 + f, dtype=np.uint8)

        # Generate realistic 33 joints from synthetic_scene
        raw_pts = pose_at(t)
        joints_3d = []
        for j_idx in range(33):
            joints_3d.append({
                "index": j_idx,
                "x": float(raw_pts[j_idx, 0]),
                "y": float(raw_pts[j_idx, 1]),
                "z": float(raw_pts[j_idx, 2]),
                "visibility": 1.0,
            })

        recorder.record_camera_frame("cam0", frame_cam0, recorder.start_time + t, world_landmarks_3d=joints_3d)
        recorder.record_camera_frame("cam1", frame_cam1, recorder.start_time + t, world_landmarks_3d=joints_3d)
        recorder.record_live_pose_3d(joints_3d, recorder.start_time + t, source_type="triangulated")

    # 3. Stop recording
    stop_res = recorder.stop_recording()
    assert stop_res["ok"] is True
    assert recorder.is_recording is False
    assert (take_dir / "cam0.mp4").exists()
    assert (take_dir / "cam1.mp4").exists()
    assert (take_dir / "take_info.json").exists()

    # 4. Process take and export to BVH
    proc_res = recorder.process_take(take_id="test_take_01", performer_height_m=1.75, smoother="savgol")
    assert proc_res["ok"] is True
    assert proc_res["bvh_exists"] is True

    bvh_path = Path(proc_res["bvh_path"])
    json_path = Path(proc_res["json_path"])

    assert bvh_path.exists()
    assert json_path.exists()
    assert bvh_path.stat().st_size > 1000

    # Verify BVH structure
    bvh_content = bvh_path.read_text(encoding="utf-8")
    assert "HIERARCHY" in bvh_content
    assert "ROOT Hip" in bvh_content
    assert "MOTION" in bvh_content
    assert "Frames:" in bvh_content

    # 5. Check recordings list
    takes = recorder.list_recordings()
    assert len(takes) >= 1
    assert any(t["take_id"] == "test_take_01" and t["has_bvh"] for t in takes)


def test_server_recording_api_endpoints(tmp_path, monkeypatch):
    # Set server live_recorder to use temp directory
    test_rec = LiveRecorder(base_output_dir=tmp_path / "server_recs")
    monkeypatch.setattr(server, "live_recorder", test_rec)
    server.camera_manager.set_recorder(test_rec)

    client = TestClient(server.app)

    # Health check should include recording status
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "recording" in data
    assert data["recording"]["is_recording"] is False

    # Status endpoint
    status_res = client.get("/api/recording/status")
    assert status_res.status_code == 200
    assert status_res.json()["is_recording"] is False

    # Recordings listing
    list_res = client.get("/api/recordings")
    assert list_res.status_code == 200
    assert "takes" in list_res.json()
