"""
Multi-camera stream manager and high-performance decoupled capture workers.
Supports USB/built-in webcams and network streams (RTSP / HTTP URLs).
Decoupled capture + inference threading prevents lag and maximizes FPS.
"""
from __future__ import annotations

import base64
import os
import platform
import threading
import time
from typing import Dict, List, Optional, Union, Any
import cv2
import numpy as np

from .detector import create_live_detector, get_best_onnx_device


def parse_source(source_val: Union[int, str]) -> Union[int, str]:
    """Converts numeric string like '0' into integer 0 for local webcam index."""
    if isinstance(source_val, str) and source_val.strip().isdigit():
        return int(source_val.strip())
    return source_val


HARDWARE_LOCK = threading.Lock()


class CameraWorker:
    """
    Decoupled capture and inference worker for one camera stream.
    Thread 1 (_capture_thread): Constantly reads newest camera frames.
    Thread 2 (_process_thread): Runs pose detection and preview encoding without stalling camera I/O.
    """
    def __init__(
        self,
        cam_id: str,
        source: Union[int, str],
        name: str = "",
        model_type: str = "mediapipe",
        model_variant: str = "full",
        device: str = "auto",
        target_fps: float = 30.0,
        preview_width: int = 640,
        jpeg_quality: int = 65,
        recorder: Optional[Any] = None,
    ):
        self.cam_id = str(cam_id)
        self.source = parse_source(source)
        self.name = name or (f"Camera {self.source}" if isinstance(self.source, int) else f"Stream {cam_id}")
        self.model_type = model_type  # "mediapipe" or "rtmpose"
        self.model_variant = model_variant  # e.g. "full", "lite", "heavy" or "balanced"
        self.device = device  # "auto", "dml", "cuda", "cpu"
        self.target_fps = target_fps
        self.preview_width = preview_width
        self.jpeg_quality = jpeg_quality
        self.recorder = recorder

        self._running = False
        self._cap_thread: Optional[threading.Thread] = None
        self._proc_thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()
        self._frame_lock = threading.Lock()

        self._cap: Optional[cv2.VideoCapture] = None
        self._detector: Optional[Any] = None

        # Decoupled newest frame slot
        self._newest_frame: Optional[np.ndarray] = None
        self._newest_frame_time: float = 0.0
        self._newest_frame_id: int = 0
        self._last_processed_id: int = -1

        # State and latest result
        self.status: str = "initializing"
        self.error_message: Optional[str] = None
        self.measured_fps: float = 0.0
        self.latency_ms: float = 0.0
        self.latest_frame_jpeg: Optional[str] = None
        self.latest_landmarks_2d: Optional[List[Dict[str, Any]]] = None
        self.latest_world_landmarks_3d: Optional[List[Dict[str, Any]]] = None
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.last_update_time: float = 0.0
        self.active_engine: str = f"{model_type} ({model_variant})"

    def start(self):
        if self._running:
            return
        self._running = True
        self.status = "starting"
        self._cap_thread = threading.Thread(target=self._capture_loop, name=f"Cap-{self.cam_id}", daemon=True)
        self._proc_thread = threading.Thread(target=self._process_loop, name=f"Proc-{self.cam_id}", daemon=True)
        self._cap_thread.start()
        self._proc_thread.start()

    def stop(self):
        self._running = False
        if self._cap_thread and self._cap_thread.is_alive():
            self._cap_thread.join(timeout=1.5)
        if self._proc_thread and self._proc_thread.is_alive():
            self._proc_thread.join(timeout=1.5)
        self.status = "stopped"

    def _open_capture(self) -> bool:
        try:
            with HARDWARE_LOCK:
                cap = None
                configured_mjpg = False
                if isinstance(self.source, int) and platform.system() == "Windows":
                    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                    params = [
                        cv2.CAP_PROP_FOURCC, fourcc,
                        cv2.CAP_PROP_FRAME_WIDTH, 1280,
                        cv2.CAP_PROP_FRAME_HEIGHT, 720,
                        cv2.CAP_PROP_FPS, int(self.target_fps or 30),
                    ]
                    try:
                        cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW, params)
                        if cap and cap.isOpened():
                            configured_mjpg = True
                    except Exception:
                        cap = None

                    if not cap or not cap.isOpened():
                        cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
                    if not cap or not cap.isOpened():
                        cap = cv2.VideoCapture(self.source)
                elif isinstance(self.source, int) and platform.system() == "Linux":
                    try:
                        cap = cv2.VideoCapture(self.source, cv2.CAP_V4L2)
                    except Exception:
                        cap = None
                    if not cap or not cap.isOpened():
                        cap = cv2.VideoCapture(self.source)
                    if cap and cap.isOpened():
                        try:
                            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                        except Exception:
                            pass
                else:
                    cap = cv2.VideoCapture(self.source)

                if not cap or not cap.isOpened():
                    self.status = "error"
                    self.error_message = f"Could not open camera source: {self.source}"
                    if cap:
                        cap.release()
                    return False

                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not configured_mjpg:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

                self._cap = cap
                self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
                self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
            return True
        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            return False

    def _capture_loop(self):
        """Dedicated high-speed thread continuously reading camera frames."""
        if not self._open_capture():
            return

        frame_counter = 0
        consecutive_errors = 0

        while self._running:
            if not self._cap or not self._cap.isOpened():
                break

            ok, frame = self._cap.read()
            if not ok or frame is None:
                # If local video file, loop back to start
                if isinstance(self.source, str) and not self.source.startswith(("rtsp://", "http://", "https://")):
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = self._cap.read()

                if not ok or frame is None:
                    consecutive_errors += 1
                    if consecutive_errors >= 90:
                        self.status = "error"
                        self.error_message = "Camera stopped sending frames"
                    time.sleep(0.01)
                    continue

            consecutive_errors = 0
            now = time.time()
            frame_counter += 1

            with self._frame_lock:
                self._newest_frame = frame
                self._newest_frame_time = now
                self._newest_frame_id = frame_counter

            # Don't spin faster than hardware capabilities
            time.sleep(0.002)

        if self._cap:
            self._cap.release()
            self._cap = None

    def _process_loop(self):
        """Inference & processing loop decoupled from camera capture."""
        try:
            self._detector = create_live_detector(
                model_type=self.model_type,
                variant=self.model_variant,
                device=self.device,
            )
            detected_device = getattr(self._detector, "device", "cpu")
            self.active_engine = f"{self.model_type} ({self.model_variant}, {detected_device})"
        except Exception as e:
            self.status = "error"
            self.error_message = f"Failed to initialize detector {self.model_type}: {e}"
            return

        self.status = "running"
        frame_count = 0
        fps_start = time.time()
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]

        while self._running:
            frame = None
            f_time = 0.0
            f_id = 0

            with self._frame_lock:
                if self._newest_frame is not None and self._newest_frame_id != self._last_processed_id:
                    frame = self._newest_frame.copy()
                    f_time = self._newest_frame_time
                    f_id = self._newest_frame_id

            if frame is None:
                time.sleep(0.005)
                continue

            self._last_processed_id = f_id
            h, w = frame.shape[:2]
            self.frame_width = w
            self.frame_height = h

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_ms = f_time * 1000.0

            # Run pose detection
            det_t0 = time.time()
            lm_2d, lm_3d = None, None
            try:
                if self._detector:
                    lm_2d, lm_3d = self._detector.detect(rgb_frame, frame_ms)
            except Exception:
                pass
            det_latency = (time.time() - det_t0) * 1000.0

            # Feed to live recorder if active
            if self.recorder and getattr(self.recorder, "is_recording", False):
                try:
                    self.recorder.record_camera_frame(self.cam_id, frame, f_time, lm_2d, lm_3d)
                except Exception:
                    pass

            # Resize preview image for transmission
            if w > self.preview_width:
                scale = self.preview_width / float(w)
                preview_h = int(h * scale)
                small_frame = cv2.resize(frame, (self.preview_width, preview_h), interpolation=cv2.INTER_LINEAR)
            else:
                small_frame = frame

            # Encode preview image as JPEG
            success, buffer = cv2.imencode(".jpg", small_frame, encode_params)
            jpeg_b64 = None
            if success:
                jpeg_b64 = base64.b64encode(buffer).decode("ascii")

            # FPS calculation
            frame_count += 1
            now = time.time()
            elapsed = now - fps_start
            if elapsed >= 1.0:
                self.measured_fps = round(frame_count / elapsed, 1)
                frame_count = 0
                fps_start = now

            with self._lock:
                self.latest_frame_jpeg = jpeg_b64
                self.latest_landmarks_2d = lm_2d
                self.latest_world_landmarks_3d = lm_3d
                self.latency_ms = round(det_latency, 1)
                self.last_update_time = now

            # Sleep slightly if processing faster than target rate
            min_interval = 1.0 / max(10.0, self.target_fps)
            proc_time = time.time() - f_time
            if proc_time < min_interval:
                time.sleep(min_interval - proc_time)

        if self._detector:
            self._detector.close()
            self._detector = None

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "cam_id": self.cam_id,
                "name": self.name,
                "source": self.source,
                "status": self.status,
                "error": self.error_message,
                "fps": self.measured_fps,
                "latency_ms": self.latency_ms,
                "engine": self.active_engine,
                "width": self.frame_width,
                "height": self.frame_height,
                "landmarks_2d": self.latest_landmarks_2d,
                "world_landmarks_3d": self.latest_world_landmarks_3d,
                "jpeg_base64": self.latest_frame_jpeg,
                "timestamp": self.last_update_time,
            }


class CameraManager:
    """
    Manages collection of active camera capture workers.
    """
    def __init__(self, recorder: Optional[Any] = None):
        self._cameras: Dict[str, CameraWorker] = {}
        self._lock = threading.Lock()
        self.recorder = recorder
        self._cached_devices: Optional[List[Dict[str, Any]]] = None
        self._cached_devices_time: float = 0.0

    def set_recorder(self, recorder: Optional[Any]):
        self.recorder = recorder
        with self._lock:
            for c in self._cameras.values():
                c.recorder = recorder

    def list_available_devices(self, max_indices: int = 6) -> List[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            if self._cached_devices is not None and (now - self._cached_devices_time < 5.0):
                updated = []
                for d in self._cached_devices:
                    in_use = any(isinstance(c.source, int) and c.source == d["index"] for c in self._cameras.values())
                    updated.append({**d, "in_use": in_use})
                return updated

        devices = []
        consecutive_failures = 0
        indices_to_probe = list(range(max_indices))

        with HARDWARE_LOCK:
            for idx in indices_to_probe:
                active = any(isinstance(c.source, int) and c.source == idx for c in self._cameras.values())
                if active:
                    devices.append({
                        "index": idx,
                        "name": f"Camera {idx} (In Use)",
                        "available": True,
                        "in_use": True,
                    })
                    consecutive_failures = 0
                    continue

                try:
                    if platform.system() == "Windows":
                        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                        if not cap.isOpened():
                            cap = cv2.VideoCapture(idx)
                    else:
                        cap = cv2.VideoCapture(idx)

                    if cap.isOpened():
                        ok, frame = cap.read()
                        if ok and frame is not None:
                            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or frame.shape[1])
                            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or frame.shape[0])
                            cap.release()
                            devices.append({
                                "index": idx,
                                "name": f"Camera {idx} ({w}x{h})",
                                "available": True,
                                "in_use": False,
                            })
                            consecutive_failures = 0
                            continue
                        cap.release()

                    if platform.system() == "Windows":
                        consecutive_failures += 1
                        if consecutive_failures >= 2:
                            break
                except Exception:
                    if platform.system() == "Windows":
                        consecutive_failures += 1
                        if consecutive_failures >= 2:
                            break

        with self._lock:
            self._cached_devices = devices
            self._cached_devices_time = now
        return devices

    def add_camera(
        self,
        cam_id: str,
        source: Union[int, str],
        name: str = "",
        model_type: str = "mediapipe",
        model_variant: str = "full",
        device: str = "auto",
    ) -> bool:
        cam_id = str(cam_id)
        parsed_src = parse_source(source)
        with self._lock:
            existing = self._cameras.get(cam_id)
            if existing and existing.status in ("starting", "running") and existing.source == parsed_src:
                return True
            if existing:
                existing.stop()

            worker = CameraWorker(
                cam_id=cam_id,
                source=parsed_src,
                name=name,
                model_type=model_type,
                model_variant=model_variant,
                device=device,
                recorder=self.recorder,
            )
            self._cameras[cam_id] = worker
            worker.start()
            return True

    def remove_camera(self, cam_id: str) -> bool:
        cam_id = str(cam_id)
        with self._lock:
            if cam_id in self._cameras:
                worker = self._cameras.pop(cam_id)
                worker.stop()
                return True
            return False

    def get_camera(self, cam_id: str) -> Optional[CameraWorker]:
        with self._lock:
            return self._cameras.get(str(cam_id))

    def get_all_snapshots(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            cams = list(self._cameras.values())
        return {c.cam_id: c.get_snapshot() for c in cams}

    def shutdown_all(self):
        with self._lock:
            workers = list(self._cameras.values())
            self._cameras.clear()
        for w in workers:
            w.stop()
