"""
Live footage recording and Mocap Pipeline BVH processing module.
Handles multi-camera synchronized video recording, real-time keypoint logging,
and seamless post-recording reconstruction to .bvh and .json via mocap_pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import cv2
import numpy as np

logger = logging.getLogger("live_recorder")

BACKEND_DIR = Path(__file__).resolve().parent.parent
RECORDINGS_DIR = BACKEND_DIR / "output" / "live_recordings"

# Ensure backend directory is on sys.path so mocap_pipeline can always be found
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from mocap_pipeline.schemas import Pose3D
except ImportError:
    try:
        from backend.mocap_pipeline.schemas import Pose3D  # type: ignore
    except ImportError:
        @dataclass
        class Pose3D:  # type: ignore
            fps: float
            points: Any
            num_views: Any


class CameraVideoWriter:
    """
    Non-blocking threaded video writer for a single camera stream.
    Uses an internal queue so writing to disk never blocks the camera capture loop.
    """
    def __init__(self, file_path: Path, fps: float = 30.0, width: int = 0, height: int = 0):
        self.file_path = Path(file_path)
        self.fps = max(10.0, float(fps))
        self.width = int(width)
        self.height = int(height)

        self._queue: queue.Queue = queue.Queue(maxsize=150)
        self._writer: Optional[cv2.VideoWriter] = None
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, name=f"Writer-{self.file_path.stem}", daemon=True)
        self._thread.start()
        self.frames_written = 0

    def _init_writer(self, w: int, h: int) -> bool:
        self.width = w
        self.height = h
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Codec candidates for mp4 / avi
        fourcc_candidates = [
            ("mp4v", self.file_path),
            ("avc1", self.file_path),
            ("MJPG", self.file_path.with_suffix(".avi")),
            ("XVID", self.file_path.with_suffix(".avi")),
        ]

        for code, path in fourcc_candidates:
            try:
                fourcc = cv2.VideoWriter_fourcc(*code)
                writer = cv2.VideoWriter(str(path), fourcc, self.fps, (w, h))
                if writer.isOpened():
                    self.file_path = path
                    self._writer = writer
                    logger.info(f"Initialized VideoWriter for {self.file_path.name} with codec '{code}' ({w}x{h} @ {self.fps} FPS)")
                    return True
                writer.release()
            except Exception as e:
                logger.debug(f"Failed codec {code}: {e}")

        logger.error(f"Could not initialize any VideoWriter codec for {self.file_path}")
        return False

    def _worker_loop(self):
        while self._running or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:
                self._queue.task_done()
                break

            frame = item
            h, w = frame.shape[:2]

            if self._writer is None:
                if not self._init_writer(w, h):
                    self._queue.task_done()
                    continue

            # Ensure frame matches initialized dimensions
            if w != self.width or h != self.height:
                frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)

            try:
                self._writer.write(frame)
                self.frames_written += 1
            except Exception as e:
                logger.warning(f"Error writing frame to {self.file_path.name}: {e}")
            finally:
                self._queue.task_done()

        if self._writer:
            self._writer.release()
            self._writer = None
            logger.info(f"Closed video writer for {self.file_path.name}: {self.frames_written} frames saved.")

    def write_frame(self, frame: np.ndarray):
        """Pushes frame into writer queue without blocking."""
        if not self._running:
            return
        try:
            self._queue.put_nowait(frame.copy())
        except queue.Full:
            # Drop frame rather than blocking camera capture loop
            logger.debug(f"Writer queue full for {self.file_path.name}, frame dropped")

    def close(self):
        self._running = False
        try:
            self._queue.put(None, timeout=0.2)
        except Exception:
            pass
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._writer:
            self._writer.release()
            self._writer = None


class LiveRecorder:
    """
    Manages live multi-camera footage recording sessions and handles
    post-recording mocap pipeline processing to BVH.
    """
    def __init__(self, base_output_dir: Optional[Path] = None):
        self.base_dir = Path(base_output_dir or RECORDINGS_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self.is_recording: bool = False
        self.is_processing: bool = False

        self.current_take_id: Optional[str] = None
        self.current_take_dir: Optional[Path] = None
        self.start_time: float = 0.0
        self.stop_time: float = 0.0

        self.writers: Dict[str, CameraVideoWriter] = {}
        self.camera_metadata: Dict[str, Dict[str, Any]] = {}
        self.frame_counts: Dict[str, int] = {}

        # Logged keypoints and live poses
        self.recorded_keypoints_2d: Dict[str, List[Dict[str, Any]]] = {}
        self.recorded_world_3d: Dict[str, List[Dict[str, Any]]] = {}
        self.recorded_poses_3d: List[Dict[str, Any]] = []

        self.last_result: Optional[Dict[str, Any]] = None

    def start_recording(
        self,
        take_id: Optional[str] = None,
        active_cameras: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Starts recording live footage for all active cameras.
        """
        with self._lock:
            if self.is_recording:
                return {
                    "ok": True,
                    "already_recording": True,
                    "take_id": self.current_take_id,
                    "take_dir": str(self.current_take_dir),
                }

            now_dt = datetime.now()
            take_id = take_id or f"take_{now_dt:%Y%m%d_%H%M%S}"
            self.current_take_id = take_id
            self.current_take_dir = self.base_dir / take_id
            self.current_take_dir.mkdir(parents=True, exist_ok=True)

            self.start_time = time.time()
            self.stop_time = 0.0
            self.writers.clear()
            self.camera_metadata.clear()
            self.frame_counts.clear()
            self.recorded_keypoints_2d.clear()
            self.recorded_world_3d.clear()
            self.recorded_poses_3d.clear()

            active_cameras = active_cameras or {}
            for cid, s in active_cameras.items():
                w = s.get("width") or 1280
                h = s.get("height") or 720
                fps = s.get("fps") or 30.0
                video_file = self.current_take_dir / f"{cid}.mp4"

                self.writers[cid] = CameraVideoWriter(video_file, fps=fps, width=w, height=h)
                self.frame_counts[cid] = 0
                self.camera_metadata[cid] = {
                    "cam_id": cid,
                    "name": s.get("name", cid),
                    "source": str(s.get("source", "")),
                    "width": w,
                    "height": h,
                    "fps": fps,
                    "video_file": str(video_file),
                }
                self.recorded_keypoints_2d[cid] = []
                self.recorded_world_3d[cid] = []

            self.is_recording = True
            logger.info(f"Started recording live take '{take_id}' with {len(self.writers)} camera(s) at {self.current_take_dir}")

            # Write initial take info
            self._save_take_info("recording")

            return {
                "ok": True,
                "take_id": self.current_take_id,
                "take_dir": str(self.current_take_dir),
                "cameras": list(self.writers.keys()),
                "start_time": self.start_time,
            }

    def record_camera_frame(
        self,
        cam_id: str,
        frame: np.ndarray,
        timestamp: float,
        landmarks_2d: Optional[List[Dict[str, Any]]] = None,
        world_landmarks_3d: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Feeds a newly captured camera frame into recording.
        """
        if not self.is_recording:
            return

        with self._lock:
            writer = self.writers.get(cam_id)
            if not writer:
                # Lazy initialization for dynamically added cameras
                if self.current_take_dir:
                    h, w = frame.shape[:2]
                    v_file = self.current_take_dir / f"{cam_id}.mp4"
                    writer = CameraVideoWriter(v_file, fps=30.0, width=w, height=h)
                    self.writers[cam_id] = writer
                    self.frame_counts[cam_id] = 0
                    self.recorded_keypoints_2d[cam_id] = []
                    self.recorded_world_3d[cam_id] = []
                    self.camera_metadata[cam_id] = {
                        "cam_id": cam_id,
                        "name": cam_id,
                        "source": "",
                        "width": w,
                        "height": h,
                        "fps": 30.0,
                        "video_file": str(v_file),
                    }
                else:
                    return

            rel_time = timestamp - self.start_time
            writer.write_frame(frame)
            self.frame_counts[cam_id] = self.frame_counts.get(cam_id, 0) + 1

            if landmarks_2d:
                self.recorded_keypoints_2d[cam_id].append({
                    "time": rel_time,
                    "frame_idx": self.frame_counts[cam_id],
                    "landmarks": landmarks_2d,
                })

            if world_landmarks_3d:
                self.recorded_world_3d[cam_id].append({
                    "time": rel_time,
                    "frame_idx": self.frame_counts[cam_id],
                    "landmarks": world_landmarks_3d,
                })

    def record_live_pose_3d(self, pose_3d_joints: List[Dict[str, Any]], timestamp: float, source_type: str = "live"):
        """
        Logs a combined/triangulated 3D pose during recording.
        """
        if not self.is_recording:
            return
        with self._lock:
            self.recorded_poses_3d.append({
                "time": timestamp - self.start_time,
                "source": source_type,
                "joints": pose_3d_joints,
            })

    def stop_recording(self) -> Dict[str, Any]:
        """
        Stops recording and finalizes all video files.
        """
        with self._lock:
            if not self.is_recording:
                return {"ok": False, "error": "Not currently recording"}

            self.is_recording = False
            self.stop_time = time.time()
            duration = max(0.1, round(self.stop_time - self.start_time, 2))

            # Close all writers cleanly
            for cid, writer in self.writers.items():
                writer.close()
                if cid in self.camera_metadata:
                    self.camera_metadata[cid]["video_file"] = str(writer.file_path)
                    self.camera_metadata[cid]["frames_written"] = writer.frames_written

            take_id = self.current_take_id
            take_dir = self.current_take_dir

            self._save_take_info("completed")
            logger.info(f"Stopped recording take '{take_id}': duration {duration}s, frames: {self.frame_counts}")

            return {
                "ok": True,
                "take_id": take_id,
                "take_dir": str(take_dir),
                "duration_s": duration,
                "frame_counts": dict(self.frame_counts),
                "cameras": list(self.writers.keys()),
                "video_paths": [str(w.file_path) for w in self.writers.values()],
            }

    def _save_take_info(self, status: str):
        if not self.current_take_dir:
            return
        info = {
            "take_id": self.current_take_id,
            "status": status,
            "start_time": self.start_time,
            "stop_time": self.stop_time,
            "duration_s": round((self.stop_time or time.time()) - self.start_time, 2),
            "cameras": self.camera_metadata,
            "frame_counts": self.frame_counts,
            "live_poses_count": len(self.recorded_poses_3d),
        }
        info_path = self.current_take_dir / "take_info.json"
        try:
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write take_info.json: {e}")

    def process_take(
        self,
        take_id: Optional[str] = None,
        calibration_path: Optional[str] = None,
        performer_height_m: float = 1.75,
        smoother: str = "savgol",
    ) -> Dict[str, Any]:
        """
        Processes recorded footage the same way as mocap_pipeline and exports it as a BVH file.
        Supports both multi-camera calibration/triangulation and single-camera MediaPipe world reconstruction.
        """
        self.is_processing = True
        try:
            target_id = take_id or self.current_take_id
            if not target_id:
                raise ValueError("No take specified to process.")

            take_dir = self.base_dir / target_id
            if not take_dir.exists():
                raise FileNotFoundError(f"Take directory not found: {take_dir}")

            info_path = take_dir / "take_info.json"
            if info_path.exists():
                with open(info_path, "r", encoding="utf-8") as f:
                    take_info = json.load(f)
            else:
                take_info = {}

            # Discover video files in take directory
            video_extensions = (".mp4", ".avi", ".mov", ".mkv")
            found_videos = [p for p in take_dir.iterdir() if p.suffix.lower() in video_extensions]
            found_videos.sort()

            if not found_videos:
                raise FileNotFoundError(f"No video files found in take directory {take_dir}")

            logger.info(f"Processing take '{target_id}' with {len(found_videos)} video(s)...")

            out_json = take_dir / "out3d.json"
            out_bvh = take_dir / "out3d.bvh"

            from mocap_pipeline.schemas import Keypoints2D, Pose3D
            from mocap_pipeline import io as p_io, config as p_cfg
            from mocap_pipeline.run_pipeline import run as run_pipeline_stages, export_bvh
            from mocap_pipeline.stage2_reconstruct import smooth
            from mocap_pipeline.joints import NUM_JOINTS, JOINT_INDEX

            bvh_exported = False
            method_used = "none"

            # Case A: Multi-camera recording (>= 2 cameras) -> Run full mocap_pipeline
            if len(found_videos) >= 2:
                try:
                    logger.info("Attempting full multi-camera mocap_pipeline run...")
                    cal_to_use = calibration_path
                    if not cal_to_use or not Path(cal_to_use).exists():
                        default_cal = BACKEND_DIR / "output" / "calibration.json"
                        if default_cal.exists():
                            cal_to_use = str(default_cal)

                    video_paths_str = [str(v) for v in found_videos]
                    clap_times_sync = [0.0] * len(found_videos)

                    run_pipeline_stages(
                        video_paths=video_paths_str,
                        out_path=str(out_json),
                        performer_height_m=performer_height_m,
                        calibration_path=cal_to_use if (cal_to_use and Path(cal_to_use).exists()) else str(take_dir / "calibration.json"),
                        clap_times=clap_times_sync,
                        bvh=True,
                        smoothing=True,
                        smoother=smoother,
                        resume=False,
                    )

                    if out_bvh.exists():
                        bvh_exported = True
                        method_used = "mocap_pipeline (multi-camera)"
                        logger.info(f"Successfully processed take with mocap_pipeline: {out_bvh}")
                except (Exception, SystemExit) as e:
                    logger.warning(f"Multi-camera run_pipeline encountered: {e}. Falling back to 3D trajectory reconstruction.")

            # Case B: Fallback or Single-Camera recording (< 2 cameras or calibration failure)
            if not bvh_exported:
                logger.info("Reconstructing 3D pose trajectory from recorded live footage...")
                pose_3d_seq = self._extract_pose3d_trajectory(found_videos, take_dir, fps=30.0)

                if pose_3d_seq is not None and len(pose_3d_seq.points) > 0:
                    # Apply smoothing
                    smoothed_pose = smooth.smooth(smooth.fill_gaps(pose_3d_seq), method=smoother)

                    # Export BVH using Stage 3 skeleton and rotation solver
                    export_bvh(smoothed_pose, str(out_bvh))

                    # Export JSON
                    timestamps = np.arange(len(smoothed_pose.points)) / smoothed_pose.fps
                    p_io.save_pose3d_json(smoothed_pose, str(out_json), timestamps)

                    bvh_exported = True
                    method_used = "live_stream_reconstruct (MediaPipe 3D)"
                    logger.info(f"Successfully reconstructed and exported BVH: {out_bvh}")
                else:
                    raise RuntimeError("Failed to extract valid 3D skeleton joints from footage.")

            result = {
                "ok": True,
                "take_id": target_id,
                "method": method_used,
                "bvh_path": str(out_bvh),
                "json_path": str(out_json),
                "video_paths": [str(v) for v in found_videos],
                "bvh_exists": out_bvh.exists(),
                "file_size_bytes": out_bvh.stat().st_size if out_bvh.exists() else 0,
            }
            self.last_result = result
            return result

        except (Exception, SystemExit) as e:
            logger.error(f"Processing take failed: {e}", exc_info=True)
            err_result = {"ok": False, "error": str(e), "take_id": take_id}
            self.last_result = err_result
            return err_result
        finally:
            self.is_processing = False

    def _extract_pose3d_trajectory(
        self,
        video_paths: List[Path],
        take_dir: Path,
        fps: float = 30.0,
    ) -> Optional[Pose3D]:
        """
        Extracts a clean (F, 33, 3) Pose3D sequence in meters, Y-up, floor at Y=0.
        Uses recorded live poses if available, or analyzes the primary recorded video.
        """
        from mocap_pipeline.joints import NUM_JOINTS, JOINT_INDEX

        # 1. If we have live recorded triangulated/3D poses in memory for this take
        if self.recorded_poses_3d and len(self.recorded_poses_3d) >= 5:
            frames = len(self.recorded_poses_3d)
            points = np.zeros((frames, NUM_JOINTS, 3), dtype=np.float64)
            num_views = np.ones((frames, NUM_JOINTS), dtype=np.float64)

            for f_idx, item in enumerate(self.recorded_poses_3d):
                joints = item.get("joints", [])
                for j_idx, j in enumerate(joints[:NUM_JOINTS]):
                    points[f_idx, j_idx, 0] = j.get("x", 0.0)
                    points[f_idx, j_idx, 1] = j.get("y", 0.0)
                    points[f_idx, j_idx, 2] = j.get("z", 0.0)
                    if j.get("visibility", 1.0) < 0.25:
                        num_views[f_idx, j_idx] = 0

            # Ground alignment: align lowest heel/ankle to Y=0
            heel_l = JOINT_INDEX.get("LEFT_HEEL", 29)
            heel_r = JOINT_INDEX.get("RIGHT_HEEL", 30)
            valid_heels = points[:, [heel_l, heel_r], 1]
            min_y = np.nanmin(valid_heels) if np.any(np.isfinite(valid_heels)) else 0.0
            points[:, :, 1] -= min_y

            return Pose3D(fps=fps, points=points, num_views=num_views)

        # 2. Extract from primary recorded video file
        primary_video = video_paths[0]
        logger.info(f"Analyzing frames from video {primary_video} for 3D landmark sequence...")

        cap = cv2.VideoCapture(str(primary_video))
        if not cap.isOpened():
            return None

        from .detector import LivePoseDetector
        detector = LivePoseDetector(model_variant="full")

        all_points = []
        all_views = []
        frame_idx = 0
        v_fps = cap.get(cv2.CAP_PROP_FPS) or fps

        try:
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_ms = frame_idx * 1000.0 / v_fps
                lm_2d, lm_3d = detector.detect(rgb, frame_ms)

                pts_frame = np.zeros((NUM_JOINTS, 3), dtype=np.float64)
                views_frame = np.zeros(NUM_JOINTS, dtype=np.float64)

                if lm_3d and len(lm_3d) >= NUM_JOINTS:
                    for i in range(NUM_JOINTS):
                        j = lm_3d[i]
                        pts_frame[i, 0] = j["x"]
                        pts_frame[i, 1] = j["y"]  # Already inverted Y-up in LivePoseDetector
                        pts_frame[i, 2] = j["z"]
                        views_frame[i] = 1 if j.get("visibility", 1.0) >= 0.3 else 0

                all_points.append(pts_frame)
                all_views.append(views_frame)
                frame_idx += 1
        finally:
            cap.release()
            detector.close()

        if not all_points:
            return None

        points_arr = np.array(all_points, dtype=np.float64)
        views_arr = np.array(all_views, dtype=np.float64)

        # Align ground floor
        heel_l = JOINT_INDEX.get("LEFT_HEEL", 29)
        heel_r = JOINT_INDEX.get("RIGHT_HEEL", 30)
        valid_heels = points_arr[:, [heel_l, heel_r], 1]
        min_y = np.nanmin(valid_heels) if np.any(np.isfinite(valid_heels)) else 0.0
        points_arr[:, :, 1] -= min_y

        return Pose3D(fps=v_fps, points=points_arr, num_views=views_arr)

    def get_status(self) -> Dict[str, Any]:
        """Returns the current recording status."""
        with self._lock:
            dur = 0.0
            if self.is_recording and self.start_time:
                dur = round(time.time() - self.start_time, 2)
            elif self.stop_time and self.start_time:
                dur = round(self.stop_time - self.start_time, 2)

            return {
                "is_recording": self.is_recording,
                "is_processing": self.is_processing,
                "take_id": self.current_take_id,
                "take_dir": str(self.current_take_dir) if self.current_take_dir else None,
                "duration_s": dur,
                "frame_counts": dict(self.frame_counts),
                "cameras": list(self.writers.keys()),
                "last_result": self.last_result,
            }

    def list_recordings(self) -> List[Dict[str, Any]]:
        """Lists all existing recordings in the recordings directory."""
        takes = []
        if not self.base_dir.exists():
            return takes

        for item in sorted(self.base_dir.iterdir(), reverse=True):
            if item.is_dir():
                info_file = item / "take_info.json"
                bvh_file = item / "out3d.bvh"
                json_file = item / "out3d.json"
                videos = [v.name for v in item.iterdir() if v.suffix.lower() in (".mp4", ".avi", ".mov")]

                info = {}
                if info_file.exists():
                    try:
                        with open(info_file, "r", encoding="utf-8") as f:
                            info = json.load(f)
                    except Exception:
                        pass

                takes.append({
                    "take_id": item.name,
                    "path": str(item),
                    "created_at": item.stat().st_mtime,
                    "has_bvh": bvh_file.exists(),
                    "bvh_size": bvh_file.stat().st_size if bvh_file.exists() else 0,
                    "has_json": json_file.exists(),
                    "videos": videos,
                    "info": info,
                })
        return takes
