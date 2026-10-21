"""
FastAPI WebSocket and REST server for live multi-camera MediaPipe mocap streaming.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn

from .camera_stream import CameraManager
from .detector import resolve_model_path, POSE_CONNECTIONS, LANDMARK_NAMES
from .filter import PoseFilter
from .triangulate_live import LiveTriangulator
from .live_recorder import LiveRecorder

logger = logging.getLogger("live_stream_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global runtime state
live_recorder = LiveRecorder()
camera_manager = CameraManager(recorder=live_recorder)
pose_filter = PoseFilter(min_cutoff=1.2, beta=0.01)
triangulator = LiveTriangulator()
active_websockets: List[WebSocket] = []
current_model_variant = "full"
filter_enabled = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(broadcast_loop())
    yield
    task.cancel()
    camera_manager.shutdown_all()


app = FastAPI(title="Mocap Live Stream API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AddCameraRequest(BaseModel):
    cam_id: str
    source: Any  # int (e.g. 0) or str (e.g. "0" or "rtsp://...")
    name: Optional[str] = ""
    model_variant: Optional[str] = None


class RemoveCameraRequest(BaseModel):
    cam_id: str


class CalibrationRequest(BaseModel):
    path: str


class FilterSettingsRequest(BaseModel):
    enabled: bool
    min_cutoff: Optional[float] = 1.2
    beta: Optional[float] = 0.01


class StartRecordingRequest(BaseModel):
    take_id: Optional[str] = None


class StopRecordingRequest(BaseModel):
    auto_process: bool = True
    performer_height_m: Optional[float] = 1.75
    smoother: Optional[str] = "savgol"


class ProcessTakeRequest(BaseModel):
    take_id: Optional[str] = None
    performer_height_m: Optional[float] = 1.75
    smoother: Optional[str] = "savgol"
    calibration_path: Optional[str] = None


async def broadcast_message(msg: dict):
    """Broadcasts arbitrary message to all active WebSocket clients."""
    dead = []
    for ws in list(active_websockets):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_websockets:
            active_websockets.remove(ws)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": current_model_variant,
        "active_cameras": len(camera_manager.get_all_snapshots()),
        "calibrated": triangulator.is_calibrated,
        "recording": live_recorder.get_status(),
    }


@app.get("/api/cameras")
async def list_cameras():
    """Returns detected physical webcam devices."""
    devices = await asyncio.to_thread(camera_manager.list_available_devices)
    return {"devices": devices}


@app.get("/api/active")
def get_active():
    """Returns status of currently active camera streams."""
    return {"cameras": camera_manager.get_all_snapshots()}


@app.post("/api/cameras/add")
def add_camera_endpoint(req: AddCameraRequest):
    model = req.model_variant or current_model_variant
    ok = camera_manager.add_camera(
        cam_id=req.cam_id,
        source=req.source,
        name=req.name or "",
        model_variant=model,
    )
    return {"ok": ok, "cam_id": req.cam_id}


@app.post("/api/cameras/remove")
def remove_camera_endpoint(req: RemoveCameraRequest):
    ok = camera_manager.remove_camera(req.cam_id)
    return {"ok": ok, "cam_id": req.cam_id}


@app.post("/api/calibration/load")
def load_calibration_endpoint(req: CalibrationRequest):
    ok = triangulator.load_calibration(req.path)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to load calibration file")
    return {"ok": True, "calibrated": True}


@app.get("/api/stream/{cam_id}")
def mjpeg_stream(cam_id: str):
    """
    MJPEG stream endpoint for direct browser/HTML embedding.
    """
    worker = camera_manager.get_camera(cam_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")

    def frame_generator():
        import base64
        while worker.status in ("running", "starting", "initializing"):
            snap = worker.get_snapshot()
            jpeg_b64 = snap.get("jpeg_base64")
            if jpeg_b64:
                frame_bytes = base64.b64decode(jpeg_b64)
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(1.0 / max(10.0, worker.target_fps))

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


# ==============================================================================
# Recording & BVH Processing Endpoints
# ==============================================================================

@app.post("/api/recording/start")
async def start_recording_endpoint(req: Optional[StartRecordingRequest] = None):
    take_id = req.take_id if req else None
    active_cams = camera_manager.get_all_snapshots()
    if not active_cams:
        raise HTTPException(status_code=400, detail="No active cameras available to record")

    res = live_recorder.start_recording(take_id=take_id, active_cameras=active_cams)
    await broadcast_message({"type": "recording_started", **res})
    return res


@app.post("/api/recording/stop")
async def stop_recording_endpoint(req: Optional[StopRecordingRequest] = None):
    res = live_recorder.stop_recording()
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to stop recording"))

    await broadcast_message({"type": "recording_stopped", **res})

    auto_process = req.auto_process if req is not None else True
    if auto_process and res.get("take_id"):
        height = req.performer_height_m if (req and req.performer_height_m) else 1.75
        smoother = req.smoother if (req and req.smoother) else "savgol"
        cal_path = triangulator.calibration_path

        await broadcast_message({"type": "processing_started", "take_id": res["take_id"]})
        proc_res = await asyncio.to_thread(
            live_recorder.process_take,
            take_id=res["take_id"],
            calibration_path=cal_path,
            performer_height_m=height,
            smoother=smoother,
        )
        res["processing"] = proc_res
        if proc_res.get("ok"):
            await broadcast_message({"type": "processing_completed", **proc_res})
        else:
            await broadcast_message({"type": "processing_error", **proc_res})

    return res


@app.post("/api/recording/process")
async def process_take_endpoint(req: ProcessTakeRequest):
    cal_path = req.calibration_path or triangulator.calibration_path
    await broadcast_message({"type": "processing_started", "take_id": req.take_id})
    proc_res = await asyncio.to_thread(
        live_recorder.process_take,
        take_id=req.take_id,
        calibration_path=cal_path,
        performer_height_m=req.performer_height_m or 1.75,
        smoother=req.smoother or "savgol",
    )
    if proc_res.get("ok"):
        await broadcast_message({"type": "processing_completed", **proc_res})
    else:
        await broadcast_message({"type": "processing_error", **proc_res})
        raise HTTPException(status_code=500, detail=proc_res.get("error", "Processing failed"))
    return proc_res


@app.get("/api/recording/status")
def recording_status_endpoint():
    return live_recorder.get_status()


@app.get("/api/recordings")
def list_recordings_endpoint():
    return {"takes": live_recorder.list_recordings()}


@app.get("/api/recording/download/{take_id}/{filename}")
def download_recording_file(take_id: str, filename: str):
    file_path = live_recorder.base_dir / take_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "application/octet-stream"
    if filename.endswith(".bvh"):
        media_type = "text/plain"
    elif filename.endswith(".json"):
        media_type = "application/json"
    elif filename.endswith((".mp4", ".m4v")):
        media_type = "video/mp4"
    return FileResponse(str(file_path), media_type=media_type, filename=filename)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected. Preparing initial setup packet...")

    # Send initial setup packet FIRST before entering broadcast loop
    devices = await asyncio.to_thread(camera_manager.list_available_devices)
    await websocket.send_json({
        "type": "init",
        "connections": POSE_CONNECTIONS,
        "landmark_names": LANDMARK_NAMES,
        "devices": devices,
        "model": current_model_variant,
        "calibrated": triangulator.is_calibrated,
    })

    # Now register for broadcast updates
    active_websockets.append(websocket)
    logger.info(f"WebSocket client initialized and active. Total clients: {len(active_websockets)}")

    try:
        while True:
            # Receive client commands
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action")

            if action == "list_devices":
                devs = await asyncio.to_thread(camera_manager.list_available_devices)
                await websocket.send_json({"type": "devices", "devices": devs})

            elif action == "add_camera":
                cam_id = msg.get("cam_id", f"cam_{int(time.time())}")
                source = msg.get("source", 0)
                name = msg.get("name", "")
                camera_manager.add_camera(
                    cam_id=cam_id,
                    source=source,
                    name=name,
                    model_variant=current_model_variant,
                )
                await websocket.send_json({"type": "camera_added", "cam_id": cam_id})

            elif action == "remove_camera":
                cam_id = msg.get("cam_id")
                if cam_id:
                    camera_manager.remove_camera(cam_id)
                    await websocket.send_json({"type": "camera_removed", "cam_id": cam_id})

            elif action == "load_calibration":
                cal_path = msg.get("path")
                if cal_path:
                    ok = triangulator.load_calibration(cal_path)
                    await websocket.send_json({"type": "calibration_loaded", "ok": ok})

            elif action == "set_filter":
                global filter_enabled
                filter_enabled = bool(msg.get("enabled", True))
                mc = msg.get("min_cutoff")
                beta = msg.get("beta")
                if mc is not None:
                    pose_filter.min_cutoff = float(mc)
                if beta is not None:
                    pose_filter.beta = float(beta)
                await websocket.send_json({"type": "filter_updated", "enabled": filter_enabled})

            elif action == "ping":
                await websocket.send_json({"type": "pong", "time": time.time()})

            elif action == "start_recording":
                take_id = msg.get("take_id")
                active_cams = camera_manager.get_all_snapshots()
                if active_cams:
                    res = live_recorder.start_recording(take_id=take_id, active_cameras=active_cams)
                    await broadcast_message({"type": "recording_started", **res})
                else:
                    await websocket.send_json({"type": "recording_error", "error": "No active cameras to record"})

            elif action == "stop_recording":
                res = live_recorder.stop_recording()
                if res.get("ok"):
                    await broadcast_message({"type": "recording_stopped", **res})
                    auto_process = msg.get("auto_process", True)
                    if auto_process and res.get("take_id"):
                        height = float(msg.get("performer_height_m", 1.75))
                        smoother = str(msg.get("smoother", "savgol"))
                        cal_path = triangulator.calibration_path
                        await broadcast_message({"type": "processing_started", "take_id": res["take_id"]})
                        proc_res = await asyncio.to_thread(
                            live_recorder.process_take,
                            take_id=res["take_id"],
                            calibration_path=cal_path,
                            performer_height_m=height,
                            smoother=smoother,
                        )
                        if proc_res.get("ok"):
                            await broadcast_message({"type": "processing_completed", **proc_res})
                        else:
                            await broadcast_message({"type": "processing_error", **proc_res})
                else:
                    await websocket.send_json({"type": "recording_error", "error": res.get("error")})

            elif action == "process_take":
                target_take = msg.get("take_id")
                height = float(msg.get("performer_height_m", 1.75))
                smoother = str(msg.get("smoother", "savgol"))
                cal_path = msg.get("calibration_path") or triangulator.calibration_path
                await broadcast_message({"type": "processing_started", "take_id": target_take})
                proc_res = await asyncio.to_thread(
                    live_recorder.process_take,
                    take_id=target_take,
                    calibration_path=cal_path,
                    performer_height_m=height,
                    smoother=smoother,
                )
                if proc_res.get("ok"):
                    await broadcast_message({"type": "processing_completed", **proc_res})
                else:
                    await broadcast_message({"type": "processing_error", **proc_res})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


async def broadcast_loop():
    """
    Broadcasts camera frames and combined 3D skeleton updates to all connected clients.
    """
    target_interval = 1.0 / 30.0  # 30 fps broadcast rate

    while True:
        t0 = time.time()
        if active_websockets:
            snapshots = camera_manager.get_all_snapshots()
            now = time.time()

            # Attempt multi-camera triangulation if calibrated
            pose_3d = None
            source_type = "none"

            if triangulator.is_calibrated and len(snapshots) >= 2:
                # Build dict of active keypoints
                cam_kps = {cid: s["landmarks_2d"] for cid, s in snapshots.items() if s.get("landmarks_2d")}
                triangulated_pts = triangulator.triangulate(cam_kps)
                if triangulated_pts:
                    pose_3d = triangulated_pts
                    source_type = "triangulated"

            # If not triangulated, use the first active camera with valid 3D world landmarks
            if pose_3d is None:
                for cid, s in snapshots.items():
                    w3d = s.get("world_landmarks_3d")
                    if w3d:
                        pose_3d = w3d
                        source_type = f"mediapipe_world ({s.get('name', cid)})"
                        break

            # Apply 1-Euro jitter filter if enabled
            if pose_3d and filter_enabled:
                pose_3d = pose_filter.filter_pose(pose_3d, now)

            # Record live 3D pose trajectory if recording
            if pose_3d and live_recorder.is_recording:
                live_recorder.record_live_pose_3d(pose_3d, now, source_type)

            # Build broadcast payload
            payload = {
                "type": "stream_update",
                "timestamp": now,
                "recording": live_recorder.get_status(),
                "cameras": {
                    cid: {
                        "cam_id": s["cam_id"],
                        "name": s["name"],
                        "source": str(s["source"]),
                        "status": s["status"],
                        "error": s["error"],
                        "fps": s["fps"],
                        "latency_ms": s["latency_ms"],
                        "width": s["width"],
                        "height": s["height"],
                        "landmarks_2d": s["landmarks_2d"],
                        "image": s["jpeg_base64"],
                    }
                    for cid, s in snapshots.items()
                },
                "pose_3d": {
                    "source": source_type,
                    "joints": pose_3d,
                } if pose_3d else None,
                "calibrated": triangulator.is_calibrated,
            }

            # Send to all connected WebSockets
            dead_sockets = []
            for ws in list(active_websockets):
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead_sockets.append(ws)

            for ws in dead_sockets:
                if ws in active_websockets:
                    active_websockets.remove(ws)

        elapsed = time.time() - t0
        sleep_time = max(0.005, target_interval - elapsed)
        await asyncio.sleep(sleep_time)


def main():
    parser = argparse.ArgumentParser(description="Live Stream MediaPipe Mocap Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on (default 8000)")
    parser.add_argument("--camera", type=str, default=None, help="Initial camera index or URL to start automatically")
    parser.add_argument("--model", choices=["lite", "full", "heavy"], default="full", help="MediaPipe model variant")
    parser.add_argument("--calibration", type=str, default=None, help="Path to calibration.json")
    parser.add_argument("--launch-gui", action="store_true", help="Launch Electron GUI automatically")

    args = parser.parse_args()

    global current_model_variant
    current_model_variant = args.model

    if args.calibration:
        triangulator.load_calibration(args.calibration)

    if args.camera is not None:
        src = int(args.camera) if args.camera.isdigit() else args.camera
        camera_manager.add_camera("cam0", src, name=f"Camera {src}", model_variant=args.model)

    if args.launch_gui:
        # Launch Electron GUI in background
        gui_dir = Path(__file__).resolve().parent / "gui"
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen("npx.cmd electron .", cwd=str(gui_dir), shell=True)
            else:
                subprocess.Popen(["npx", "electron", "."], cwd=str(gui_dir), shell=False)
        except Exception as e:
            logger.warning(f"Could not auto-launch Electron GUI: {e}")

    logger.info(f"Starting Live Stream Server on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
