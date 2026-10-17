"""
HTTP API around the mocap pipeline, for the web frontend.

    cd backend
    python -m pip install -r requirements-api.txt
    uvicorn api:app

Upload 2 or more videos as a take, the pipeline runs on it in the background (one
take at a time, each in its own process), then fetch out3d.json / out3d.bvh.

Each take lives in backend/output/<take_id>/:
    cam0.mov, cam1.mp4, ...   the uploads (camera order, bytes unchanged)
    status.json               the take record returned by the API
    log.txt                   everything the pipeline printed
    calibration.json, out3d.json, out3d.bvh   pipeline outputs
    out3d.metrics.json, out3d.log             quality numbers and the pipeline's own log

Environment variables:
    MOCAP_MAX_UPLOAD_MB   max size per video in MB (default 800)
    MOCAP_CORS_ORIGINS    allowed origins, comma-separated (default: the Vite dev server)

Importing this file must have no side effects: the worker processes are
started with spawn and re-import it.
"""
from __future__ import annotations

import json
import math
import multiprocessing
import os
import queue
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import traceback
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from python_multipart.multipart import MultipartParser, parse_options_header
except ImportError:  # python-multipart older than 0.0.13
    from multipart.multipart import MultipartParser, parse_options_header

from mocap_pipeline import config
from mocap_pipeline.run_pipeline import OUTPUT_DIR, run

TAKE_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
VIDEO_EXTENSIONS = {".mov", ".mp4"}
# video fields are cam0, cam1, ... with no gaps; any number from config.MIN_CAMERAS up
CAMERA_FIELD_RE = re.compile(r"^cam(\d+)$")
MAX_NAME_LENGTH = 100
# projects only live in the frontend mock data for now, so any well-formed id is accepted
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
MIN_HEIGHT_M, MAX_HEIGHT_M = 1.0, 2.5
MAX_TEXT_FIELD_BYTES = 1024
# Vite dev server (frontend/vite.config.ts: server.port 5173)
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

# printed line prefix -> stage shown to the user (sync prints nothing until it
# finishes, so it falls under detecting)
STAGE_PREFIXES = [("Detecting joints in", "detecting"), ("Clap at", "calibrating"),
                  ("Saved calibration", "triangulating")]


# ---- take records --------------------------------------------------------------

def take_dir(take_id: str) -> Path:
    return OUTPUT_DIR / take_id


def new_take_id() -> str:
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _retry_sharing(action, attempts: int = 50, pause_s: float = 0.005):
    """
    Runs action(), retrying briefly on OSError. On Windows a file that another
    process has open cannot be replaced, and a file being replaced cannot be
    opened, so the API's reads and the worker's writes of status.json can
    collide for a few milliseconds. The last error is raised.
    """
    for attempt in range(attempts):
        try:
            return action()
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(pause_s)


def write_status(folder: Path, record: dict) -> None:
    """Atomic: the API reads status.json while the worker writes it."""
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".status-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fp:
            json.dump(record, fp, indent=2)
        _retry_sharing(lambda: os.replace(tmp, folder / "status.json"))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _load_json(path: Path) -> dict:
    with open(path) as fp:
        return json.load(fp)


def read_status(folder: Path) -> dict | None:
    try:
        record = _retry_sharing(lambda: _load_json(folder / "status.json"))
    except (OSError, ValueError):
        return None
    record.setdefault("project_id", None)  # takes recorded before project_id existed
    return record


def update_status(folder: Path, **fields) -> None:
    record = read_status(folder)
    if record is not None:
        record.update(fields)
        write_status(folder, record)


def get_take(take_id: str) -> tuple[Path, dict]:
    """The take's folder and record, or 404 (also for ids that aren't ours)."""
    if not TAKE_ID_RE.match(take_id):
        raise HTTPException(404, "take not found")
    folder = take_dir(take_id)
    record = read_status(folder)
    if record is None:
        raise HTTPException(404, "take not found")
    return folder, record


# ---- worker (runs in its own process) --------------------------------------------

class LogWriter:
    """Stands in for sys.stdout: appends each line to log.txt and updates the stage."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.log = open(folder / "log.txt", "a", encoding="utf-8")
        self.partial = ""

    def write(self, text: str) -> int:
        self.partial += text
        *lines, self.partial = self.partial.split("\n")
        for line in lines:
            self._line(line)
        return len(text)

    def flush(self) -> None:
        self.log.flush()

    def close(self) -> None:
        if self.partial:
            self._line(self.partial)
            self.partial = ""
        self.log.close()

    def _line(self, line: str) -> None:
        self.log.write(line + "\n")
        self.log.flush()
        stage = next((s for prefix, s in STAGE_PREFIXES if line.startswith(prefix)), None)
        if line.startswith("Saved ") and "frames of 3D joints" in line:
            stage = "writing"
        if stage:
            update_status(self.folder, stage=stage)


def run_take(folder_str: str, video_paths: list[str], height_m: float) -> None:
    """One take, start to finish. Top-level so the spawned process can import it."""
    folder = Path(folder_str)
    update_status(folder, status="running", stage=None)

    writer = LogWriter(folder)
    stdout = sys.stdout
    sys.stdout = writer
    try:
        run(video_paths, out_path=str(folder / "out3d.json"), performer_height_m=height_m,
            calibration_path=str(folder / "calibration.json"), recalibrate=True)
        result = {"status": "done", "stage": None, "error": None}
    except SystemExit as e:
        print(f"FAILED: {e.code}")
        result = {"status": "failed", "error": str(e.code)}
    except Exception as e:
        print(traceback.format_exc())
        result = {"status": "failed", "error": str(e)}
    finally:
        sys.stdout = stdout
        writer.close()

    update_status(folder, finished_at=now_iso(), **result)


# ---- job queue (API process) -------------------------------------------------------
# ProcessPoolExecutor hands a couple of jobs to its worker ahead of time, and those
# can no longer be cancelled. So queued takes wait here, each with its own Future
# that DELETE can cancel, and the dispatcher thread gives the pool one at a time.

def new_executor() -> ProcessPoolExecutor:
    # spawn, not fork: forking a running uvicorn and then loading MediaPipe can hang
    return ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))


def mark_interrupted() -> None:
    """Takes left queued/running by a previous server never finished."""
    if not OUTPUT_DIR.is_dir():
        return
    for folder in OUTPUT_DIR.iterdir():
        record = read_status(folder) if TAKE_ID_RE.match(folder.name) else None
        if record and record.get("status") in ("queued", "running"):
            update_status(folder, status="failed", error="interrupted: server restarted",
                          finished_at=now_iso())


def dispatch(state) -> None:
    """Dispatcher thread: runs queued takes on the pool, one at a time, in order."""
    while True:
        item = state.queue.get()
        if item is None:
            return
        future, args = item
        if not future.set_running_or_notify_cancel():
            continue  # cancelled while queued
        try:
            try:
                job = state.executor.submit(run_take, *args)
            except BrokenProcessPool:
                # the last worker died hard (e.g. crashed inside MediaPipe); start a fresh pool
                state.executor = new_executor()
                job = state.executor.submit(run_take, *args)
            future.set_result(job.result())
        except BaseException as e:
            future.set_exception(e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mark_interrupted()
    app.state.executor = new_executor()
    app.state.jobs = {}  # take_id -> Future, so queued takes can be cancelled
    app.state.queue = queue.Queue()
    dispatcher = threading.Thread(target=dispatch, args=(app.state,), daemon=True)
    dispatcher.start()
    yield
    for future in list(app.state.jobs.values()):
        future.cancel()
    app.state.queue.put(None)
    stop_workers(app.state.executor)


def stop_workers(executor: ProcessPoolExecutor) -> None:
    """Server stopping: kill a take that is still running (marked failed on the next start)."""
    terminate = getattr(executor, "terminate_workers", None)  # Python 3.14+
    if terminate:
        terminate()
        return
    # shutdown() forgets the processes, so take them first
    processes = list((getattr(executor, "_processes", None) or {}).values())
    executor.shutdown(wait=False, cancel_futures=True)
    for process in processes:
        process.terminate()


app = FastAPI(title="Mocap pipeline API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("MOCAP_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
                   if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


def submit(take_id: str, video_paths: list[str], height_m: float) -> None:
    folder = take_dir(take_id)
    future = Future()
    app.state.jobs[take_id] = future

    def finished(f: Future) -> None:
        app.state.jobs.pop(take_id, None)
        if f.cancelled():
            return
        error = f.exception()
        # run_take handles pipeline errors itself; this is the worker process dying
        if error is not None and (read_status(folder) or {}).get("status") in ("queued", "running"):
            update_status(folder, status="failed", error=f"worker process failed: {error!r}",
                          finished_at=now_iso())

    future.add_done_callback(finished)
    app.state.queue.put((future, (str(folder), video_paths, height_m)))


def delete_take(take_id: str) -> str:
    """'deleted', 'running' or 'not_found'."""
    if not TAKE_ID_RE.match(take_id):
        return "not_found"
    folder = take_dir(take_id)
    record = read_status(folder)
    if record is None:
        return "not_found"

    if record.get("status") in ("queued", "running"):
        future = app.state.jobs.get(take_id)
        # cancel() fails once the job has started
        if record["status"] == "running" or future is None or not future.cancel():
            return "running"

    shutil.rmtree(folder, ignore_errors=True)
    return "deleted"


# ---- upload --------------------------------------------------------------------------

class UploadError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code, self.detail = status_code, detail


class TakeUpload:
    """
    Streams a multipart body straight into the take folder: each video is written
    in chunks and the upload stops as soon as one passes the size limit.
    """

    def __init__(self, folder: Path, boundary: bytes, max_bytes: int):
        self.folder, self.max_bytes = folder, max_bytes
        self.videos: dict[str, Path] = {}
        self.fields: dict[str, str] = {}
        self.error: UploadError | None = None
        self._header_field = self._header_value = b""
        self._headers: dict[bytes, bytes] = {}
        self._name = None
        self._file = None
        self._text = None
        self._size = 0
        self.parser = MultipartParser(boundary, {
            "on_part_begin": self._part_begin, "on_header_field": self._header_field_data,
            "on_header_value": self._header_value_data, "on_header_end": self._header_end,
            "on_headers_finished": self._headers_finished, "on_part_data": self._part_data,
            "on_part_end": self._part_end,
        })

    def fail(self, status_code: int, detail: str) -> None:
        if self.error is None:
            self.error = UploadError(status_code, detail)
        self.close()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def write(self, chunk: bytes) -> None:
        self.parser.write(chunk)

    def _part_begin(self) -> None:
        self._headers, self._name, self._text, self._size = {}, None, None, 0

    def _header_field_data(self, data, start, end) -> None:
        self._header_field += data[start:end]

    def _header_value_data(self, data, start, end) -> None:
        self._header_value += data[start:end]

    def _header_end(self) -> None:
        self._headers[self._header_field.lower()] = self._header_value
        self._header_field = self._header_value = b""

    def _headers_finished(self) -> None:
        if self.error:
            return
        _, options = parse_options_header(self._headers.get(b"content-disposition", b""))
        name = options.get(b"name", b"").decode("utf-8", "replace")
        filename = options.get(b"filename")
        if name in self.videos or name in self.fields:
            return self.fail(422, f"{name} given more than once")
        self._name = name

        if filename is None:
            if CAMERA_FIELD_RE.match(name):
                return self.fail(422, f"{name} must be a video file")
            self._text = b""
            return

        if not CAMERA_FIELD_RE.match(name):
            return self.fail(422, f"unexpected file field {name!r}; videos go in cam0, cam1, ...")
        ext = Path(filename.decode("utf-8", "replace")).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            return self.fail(422, f"{name}: only .mov and .mp4 videos are accepted")
        path = self.folder / f"{name}{ext}"
        self.videos[name] = path
        self._file = open(path, "wb")

    def _part_data(self, data, start, end) -> None:
        if self.error:
            return
        self._size += end - start
        if self._file:
            if self._size > self.max_bytes:
                return self.fail(413, f"{self._name} is larger than {self.max_bytes // (1024 * 1024)} MB")
            self._file.write(data[start:end])
        elif self._text is not None:
            if self._size > MAX_TEXT_FIELD_BYTES:
                return self.fail(422, f"{self._name} is too long")
            self._text += data[start:end]

    def _part_end(self) -> None:
        if self.error:
            return
        if self._file:
            self._file.close()
            self._file = None
        elif self._text is not None:
            self.fields[self._name] = self._text.decode("utf-8", "replace")
            self._text = None


def camera_number(field: str) -> int:
    """cam12 -> 12, so camera fields sort numerically rather than as text."""
    return int(CAMERA_FIELD_RE.match(field).group(1))


def check_upload(upload: TakeUpload) -> tuple[list[str], float, str | None, str | None]:
    """Video paths in camera order, height, name, project id; raises UploadError (422)."""
    n = len(upload.videos)
    expected = [f"cam{c}" for c in range(n)]
    if n < config.MIN_CAMERAS or sorted(upload.videos, key=camera_number) != expected:
        raise UploadError(422, f"give at least {config.MIN_CAMERAS} videos as cam0, cam1, ... with no gaps "
                               f"(got {', '.join(sorted(upload.videos, key=camera_number)) or 'none'})")

    unknown = set(upload.fields) - {"height_m", "name", "project_id"}
    if unknown:
        raise UploadError(422, f"unexpected field(s): {', '.join(sorted(unknown))}")

    try:
        height_m = float(upload.fields["height_m"])
    except KeyError:
        raise UploadError(422, "height_m is required")
    except ValueError:
        raise UploadError(422, "height_m must be a number (metres)")
    if not math.isfinite(height_m) or not MIN_HEIGHT_M <= height_m <= MAX_HEIGHT_M:
        raise UploadError(422, f"height_m must be between {MIN_HEIGHT_M} and {MAX_HEIGHT_M} metres")

    name = upload.fields.get("name", "").strip() or None
    if name and len(name) > MAX_NAME_LENGTH:
        raise UploadError(422, f"name is longer than {MAX_NAME_LENGTH} characters")

    project_id = upload.fields.get("project_id", "").strip() or None
    if project_id and not PROJECT_ID_RE.match(project_id):
        raise UploadError(422, "project_id must be up to 100 letters, digits, - or _")

    return [str(upload.videos[c]) for c in expected], height_m, name, project_id


# ---- endpoints -------------------------------------------------------------------------

@app.post("/takes", status_code=202)
async def create_take(request: Request) -> dict:
    content_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary:
        raise HTTPException(422, "send the take as multipart/form-data")

    take_id = new_take_id()
    folder = take_dir(take_id)
    folder.mkdir(parents=True)
    max_bytes = int(float(os.getenv("MOCAP_MAX_UPLOAD_MB", "800")) * 1024 * 1024)
    upload = TakeUpload(folder, boundary, max_bytes)
    try:
        try:
            async for chunk in request.stream():
                upload.write(chunk)
                if upload.error:
                    break
        except Exception as e:  # malformed body or client disconnected
            upload.fail(422, f"could not read the upload: {e}")
        upload.close()
        if upload.error:
            raise upload.error
        video_paths, height_m, name, project_id = check_upload(upload)
    except UploadError as e:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(e.status_code, e.detail)

    record = {"id": take_id, "name": name, "project_id": project_id, "created_at": now_iso(),
              "camera_count": len(video_paths), "height_m": height_m, "status": "queued", "stage": None,
              "error": None, "finished_at": None}
    write_status(folder, record)
    submit(take_id, video_paths, height_m)
    return record


@app.get("/takes")
def list_takes(project_id: str | None = None) -> list[dict]:
    """Every take, newest first; ?project_id= keeps only that project's takes."""
    if not OUTPUT_DIR.is_dir():
        return []
    ids = sorted((d.name for d in OUTPUT_DIR.iterdir() if TAKE_ID_RE.match(d.name)), reverse=True)
    records = [r for r in (read_status(take_dir(i)) for i in ids) if r is not None]
    return [r for r in records if r["project_id"] == project_id] if project_id else records


@app.get("/takes/{take_id}")
def get_take_record(take_id: str) -> dict:
    return get_take(take_id)[1]


def result_file(take_id: str, filename: str, media_type: str) -> FileResponse:
    folder, record = get_take(take_id)
    if record.get("status") != "done":
        raise HTTPException(409, f"take is {record.get('status')}, not done")
    path = folder / filename
    if not path.is_file():
        raise HTTPException(404, f"{filename} not found")
    return FileResponse(path, media_type=media_type, filename=filename)


@app.get("/takes/{take_id}/out3d.json")
def get_out3d_json(take_id: str) -> FileResponse:
    return result_file(take_id, "out3d.json", "application/json")


@app.get("/takes/{take_id}/out3d.bvh")
def get_out3d_bvh(take_id: str) -> FileResponse:
    return result_file(take_id, "out3d.bvh", "text/plain")


@app.get("/takes/{take_id}/metrics.json")
def get_metrics(take_id: str) -> FileResponse:
    """Quality numbers for the take (mocap_pipeline/metrics.py); written for failed takes too."""
    folder, record = get_take(take_id)
    if record.get("status") not in ("done", "failed"):
        raise HTTPException(409, f"take is {record.get('status')}, not finished")
    path = folder / "out3d.metrics.json"
    if not path.is_file():
        raise HTTPException(404, "metrics.json not found")
    return FileResponse(path, media_type="application/json", filename="metrics.json")


@app.delete("/takes/{take_id}", status_code=204)
def delete_one(take_id: str) -> Response:
    result = delete_take(take_id)
    if result == "not_found":
        raise HTTPException(404, "take not found")
    if result == "running":
        raise HTTPException(409, "take is running; wait until it finishes")
    return Response(status_code=204)


class DeleteRequest(BaseModel):
    ids: list[str]


@app.post("/takes/delete")
def delete_many(body: DeleteRequest) -> dict:
    return {"results": {take_id: delete_take(take_id) for take_id in body.ids}}
