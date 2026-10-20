"""
Multi-camera stream manager and non-blocking capture workers.
Supports USB/built-in webcams (device indices) and network streams (RTSP / HTTP URLs).
"""
import base64
import os
import platform
import threading
import time
from typing import Dict, List, Optional, Union, Any
import cv2
import numpy as np

from .detector import LivePoseDetector


def parse_source(source_val: Union[int, str]) -> Union[int, str]:
    """Converts numeric string like '0' into integer 0 for local webcam index."""
    if isinstance(source_val, str) and source_val.strip().isdigit():
        return int(source_val.strip())
    return source_val


HARDWARE_LOCK = threading.Lock()


class CameraWorker:
    """
    Dedicated thread for capturing and processing frames from one camera source.
    """
    def __init__(
        self,
        cam_id: str,
        source: Union[int, str],
        name: str = "",
        model_variant: str = "full",
        target_fps: float = 30.0,
        preview_width: int = 640,
        jpeg_quality: int = 65,
    ):
        self.cam_id = str(cam_id)
        self.source = parse_source(source)
        self.name = name or (f"Camera {self.source}" if isinstance(self.source, int) else f"Stream {cam_id}")
        self.model_variant = model_variant
        self.target_fps = target_fps
        self.preview_width = preview_width
        self.jpeg_quality = jpeg_quality

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._cap: Optional[cv2.VideoCapture] = None
        self._detector: Optional[LivePoseDetector] = None

        # State and latest result
        self.status: str = "initializing"  # "initializing", "running", "error", "stopped"
        self.error_message: Optional[str] = None
        self.measured_fps: float = 0.0
        self.latency_ms: float = 0.0
        self.latest_frame_jpeg: Optional[str] = None
        self.latest_landmarks_2d: Optional[List[Dict[str, Any]]] = None
        self.latest_world_landmarks_3d: Optional[List[Dict[str, Any]]] = None
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.last_update_time: float = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self.status = "starting"
        self._thread = threading.Thread(target=self._capture_loop, name=f"CamWorker-{self.cam_id}", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.status = "stopped"

    def _open_capture(self) -> bool:
        try:
            with HARDWARE_LOCK:
                cap = None
                configured_mjpg = False
                if isinstance(self.source, int) and platform.system() == "Windows":
                    # Pass initial MJPG parameters into DirectShow constructor.
                    # On USB 2.0 webcams, uncompressed YUY2 is hardware-throttled
                    # to 10 FPS at 720p due to USB bandwidth. Initializing DirectShow pins directly with
                    # MJPG unlocks full 30 FPS!
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
                    # On Linux, try V4L2 backend first, then fallback to default
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

                # Set buffer size to 1 to reduce lag on live streams
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Only call cap.set for width/height if not already configured via DSHOW MJPG constructor,
                # because in Windows DirectShow, calling cap.set(FRAME_WIDTH) will renegotiate the pin
                # and silently revert MJPG back to uncompressed YUY2 (which caps at 10 FPS)!
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
        if not self._open_capture():
            return

        try:
            self._detector = LivePoseDetector(model_variant=self.model_variant)
        except Exception as e:
            self.status = "error"
            self.error_message = f"Failed to initialize MediaPipe detector: {e}"
            if self._cap:
                self._cap.release()
            return

        self.status = "running"
        frame_count = 0
        fps_start_time = time.time()
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        consecutive_read_errors = 0

        while self._running:
            t0 = time.time()
            ok, frame = self._cap.read()
            if not ok or frame is None:
                # If source is a local video file, loop back to start for continuous live stream testing
                if isinstance(self.source, str) and not self.source.startswith(("rtsp://", "http://", "https://")):
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = self._cap.read()
                if not ok or frame is None:
                    consecutive_read_errors += 1
                    if consecutive_read_errors >= 90:
                        self.status = "error"
                        self.error_message = "Camera stopped sending frames"
                    time.sleep(0.01)
                    continue
            consecutive_read_errors = 0

            h, w = frame.shape[:2]
            self.frame_width = w
            self.frame_height = h

            # MediaPipe expects RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_ms = time.time() * 1000.0

            # Detect landmarks safely
            det_t0 = time.time()
            lm_2d, lm_3d = None, None
            try:
                if self._detector:
                    lm_2d, lm_3d = self._detector.detect(rgb_frame, frame_ms)
            except Exception:
                pass
            det_latency = (time.time() - det_t0) * 1000.0

            # Resize for lightweight preview transmission over WebSocket
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
            elapsed = now - fps_start_time
            if elapsed >= 1.0:
                self.measured_fps = round(frame_count / elapsed, 1)
                frame_count = 0
                fps_start_time = now

            with self._lock:
                self.latest_frame_jpeg = jpeg_b64
                self.latest_landmarks_2d = lm_2d
                self.latest_world_landmarks_3d = lm_3d
                self.latency_ms = round(det_latency, 1)
                self.last_update_time = now

            # Sleep slightly if needed to avoid burning 100% CPU on fast cameras
            frame_time = time.time() - t0
            min_frame_time = 1.0 / max(10.0, self.target_fps)
            if frame_time < min_frame_time:
                time.sleep(min_frame_time - frame_time)

        # Cleanup
        if self._cap:
            self._cap.release()
            self._cap = None
        if self._detector:
            self._detector.close()
            self._detector = None

    def get_snapshot(self) -> Dict[str, Any]:
        """Returns the latest processed state for this camera."""
        with self._lock:
            return {
                "cam_id": self.cam_id,
                "name": self.name,
                "source": self.source,
                "status": self.status,
                "error": self.error_message,
                "fps": self.measured_fps,
                "latency_ms": self.latency_ms,
                "width": self.frame_width,
                "height": self.frame_height,
                "landmarks_2d": self.latest_landmarks_2d,
                "world_landmarks_3d": self.latest_world_landmarks_3d,
                "jpeg_base64": self.latest_frame_jpeg,
                "timestamp": self.last_update_time,
            }


class CameraManager:
    """
    Manages multiple active camera streams.
    """
    def __init__(self):
        self._cameras: Dict[str, CameraWorker] = {}
        self._lock = threading.Lock()
        self._cached_devices: Optional[List[Dict[str, Any]]] = None
        self._cached_devices_time: float = 0.0

    def list_available_devices(self, max_indices: int = 6) -> List[Dict[str, Any]]:
        """
        Quickly probes local webcam indices to see which ones are physically present and functional.
        Caches results for 5 seconds to prevent COM/DirectShow collisions.
        """
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

        # On Linux, inspect /sys/class/video4linux to discover real device nodes
        if platform.system() == "Linux":
            import glob
            sysfs_paths = glob.glob("/sys/class/video4linux/video*")
            if sysfs_paths:
                indices = []
                for p in sysfs_paths:
                    base = os.path.basename(p)
                    if base.startswith("video") and base[5:].isdigit():
                        indices.append(int(base[5:]))
                indices.sort()
                # Limit scan to first 16 devices to avoid long latency on machines with multi-node ISP/ISYS
                indices_to_probe = indices[:16]
            else:
                indices_to_probe = list(range(max_indices))
        else:
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

                sysfs_name = ""
                if platform.system() == "Linux":
                    name_file = f"/sys/class/video4linux/video{idx}/name"
                    if os.path.exists(name_file):
                        try:
                            with open(name_file, "r") as f:
                                sysfs_name = f.read().strip()
                        except Exception:
                            pass

                try:
                    if platform.system() == "Windows":
                        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                        if not cap.isOpened():
                            cap = cv2.VideoCapture(idx)
                    elif platform.system() == "Linux":
                        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
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
                            label = f"{sysfs_name} ({w}x{h})" if sysfs_name else f"Camera {idx} ({w}x{h})"
                            devices.append({
                                "index": idx,
                                "name": label,
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
        model_variant: str = "full",
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
                model_variant=model_variant,
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
