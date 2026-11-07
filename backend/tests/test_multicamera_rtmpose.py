"""
Test multi-camera concurrent streaming with RTMPose (DirectML / CPU) and MediaPipe,
verifying hot-swapping engines and dynamic camera addition / removal without deadlocks or crashes.
"""
import time
from unittest.mock import MagicMock
import numpy as np
import pytest
try:
    from backend.live_stream_test.camera_stream import CameraManager, CameraWorker
    from backend.live_stream_test.detector import get_best_onnx_device
except ImportError:
    from live_stream_test.camera_stream import CameraManager, CameraWorker
    from live_stream_test.detector import get_best_onnx_device


def make_mock_capture():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    dummy_frame = (np.random.rand(480, 640, 3) * 255).astype(np.uint8)
    mock_cap.read.return_value = (True, dummy_frame)
    mock_cap.get.side_effect = lambda prop: 640 if prop == 3 else (480 if prop == 4 else 30)
    return mock_cap


def wait_until(condition_fn, timeout=4.0, interval=0.05):
    start = time.time()
    while time.time() - start < timeout:
        if condition_fn():
            return True
        time.sleep(interval)
    return False


def test_multicamera_rtmpose_concurrency():
    best_device = get_best_onnx_device()
    print(f"Testing multi-camera RTMPose on device: {best_device}")

    manager = CameraManager()

    w1 = CameraWorker(
        cam_id="cam_test_1",
        source="mock_1",
        name="Camera 1",
        model_type="rtmpose",
        model_variant="balanced",
        device=best_device,
    )
    w2 = CameraWorker(
        cam_id="cam_test_2",
        source="mock_2",
        name="Camera 2",
        model_type="rtmpose",
        model_variant="balanced",
        device=best_device,
    )

    # Mock _open_capture to return mock_cap
    w1._open_capture = lambda: setattr(w1, "_cap", make_mock_capture()) or True
    w2._open_capture = lambda: setattr(w2, "_cap", make_mock_capture()) or True

    w1.start()
    w2.start()

    manager._cameras["cam_test_1"] = w1
    manager._cameras["cam_test_2"] = w2

    # Wait for initial model load and first processed frames
    assert wait_until(lambda: w1.latest_frame_jpeg is not None and w2.latest_frame_jpeg is not None, timeout=5.0)

    # Check status
    snap1 = w1.get_snapshot()
    snap2 = w2.get_snapshot()
    assert snap1["status"] in ("running", "starting")
    assert snap2["status"] in ("running", "starting")
    assert snap1["error"] is None
    assert snap2["error"] is None
    assert snap1["jpeg_base64"] is not None
    assert snap2["jpeg_base64"] is not None

    # Hot-swap both engines on the fly to MediaPipe
    results = manager.switch_all_engines("mediapipe", "full", "cpu")
    assert results.get("cam_test_1") is True
    assert results.get("cam_test_2") is True
    assert "mediapipe" in w1.active_engine
    assert "mediapipe" in w2.active_engine

    # Let MediaPipe inference run concurrently on both feeds
    time.sleep(0.5)

    assert w1.error_message is None
    assert w2.error_message is None

    # Hot-swap back to RTMPose on GPU
    results_rtm = manager.switch_all_engines("rtmpose", "balanced", best_device)
    assert results_rtm.get("cam_test_1") is True
    assert results_rtm.get("cam_test_2") is True
    assert "rtmpose" in w1.active_engine
    assert "rtmpose" in w2.active_engine

    # Let RTMPose run again
    time.sleep(0.5)

    assert w1.error_message is None
    assert w2.error_message is None

    # Remove Camera 1 dynamically
    ok_rem = manager.remove_camera("cam_test_1")
    assert ok_rem is True
    assert "cam_test_1" not in manager._cameras
    assert w1.status == "stopped"

    # Add Camera 3 dynamically
    w3 = CameraWorker(
        cam_id="cam_test_3",
        source="mock_3",
        name="Camera 3",
        model_type="rtmpose",
        model_variant="balanced",
        device=best_device,
    )
    w3._open_capture = lambda: setattr(w3, "_cap", make_mock_capture()) or True
    w3.start()
    manager._cameras["cam_test_3"] = w3

    assert wait_until(lambda: w3.latest_frame_jpeg is not None, timeout=4.0)

    assert w2.error_message is None
    assert w3.error_message is None
    snap3 = w3.get_snapshot()
    assert snap3["error"] is None
    assert snap3["jpeg_base64"] is not None

    manager.shutdown_all()
    assert len(manager._cameras) == 0
