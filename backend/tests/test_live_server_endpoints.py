"""
Unit tests for live_stream_test server endpoints:
  - Model engine switching (MediaPipe / RTMPose)
  - T-pose auto-calibration reset & trigger
  - Root motion mode toggling
"""
from fastapi.testclient import TestClient
import pytest

from live_stream_test import server


@pytest.fixture
def client():
    return TestClient(server.app)


def test_health_reports_engine_and_device(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "model_type" in data
    assert "device" in data
    assert "tpose_calibrated" in data


def test_set_root_motion_endpoint(client):
    res = client.post("/api/root_motion", json={"mode": "root_locked"})
    assert res.status_code == 200
    assert res.json()["mode"] == "root_locked"
    assert server.root_tracker.mode == "root_locked"

    res2 = client.post("/api/root_motion", json={"mode": "global"})
    assert res2.status_code == 200
    assert res2.json()["mode"] == "global"
    assert server.root_tracker.mode == "global"


def test_tpose_reset_endpoint(client):
    res = client.post("/api/tpose/reset")
    assert res.status_code == 200
    assert server.auto_tpose_calibrator.state == "idle"
    assert server.auto_tpose_calibrator.calibration_data is None


def test_set_model_engine_endpoint(client):
    res = client.post("/api/model/engine", json={
        "model_type": "rtmpose",
        "model_variant": "balanced",
        "device": "auto",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["model_type"] == "rtmpose"
    assert server.current_model_type == "rtmpose"
