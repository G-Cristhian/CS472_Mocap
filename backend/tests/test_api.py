"""
api.py through FastAPI's test client, with no pipeline and no worker process:
the process pool is replaced by threads that can be held at a gate, and
run_pipeline.run by a stand-in that writes the result files (or fails).

Covers upload parsing, the take record, the one-at-a-time queue, cancelling
a queued take, refusing to delete a running one, the result and metrics
routes, and the restart recovery that marks interrupted takes failed.
"""
import json
import os
import threading
import time
from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from mocap_pipeline import io  # noqa: E402
from mocap_pipeline.joints import EXTRA_JOINTS, JOINTS, MEDIAPIPE_JOINTS, NUM_JOINTS  # noqa: E402
from tests.conftest import make_keypoints, make_sync  # noqa: E402

VIDEO = b"\x00\x00\x00\x18ftypmp42" + b"not really a video" * 4


# ---- stand-ins -------------------------------------------------------------------

class ThreadExecutor:
    """Runs submitted jobs in threads, in this process, so monkeypatched api.run is what runs."""

    def __init__(self, break_first: bool = False):
        self.break_first = break_first
        self.submitted = 0

    def submit(self, fn, *args):
        self.submitted += 1
        if self.break_first and self.submitted == 1:
            raise BrokenProcessPool("worker died")
        future = Future()

        def work():
            try:
                future.set_result(fn(*args))
            except BaseException as e:  # pragma: no cover - surfaced through the future
                future.set_exception(e)

        threading.Thread(target=work, daemon=True).start()
        return future

    def shutdown(self, wait=False, cancel_futures=False):
        pass


def fake_run(video_paths, out_path, performer_height_m=None, calibration_path=None, recalibrate=False, **kw):
    """Stands in for run_pipeline.run: prints a stage line, writes the result files."""
    print(f"Detecting joints in {video_paths[0]} (mediapipe)")
    out = Path(out_path)
    ids = [Path(v).stem for v in video_paths]
    for cid, video in zip(ids, video_paths):           # stage 1 and 2a files, as the real run leaves them
        io.save_keypoints(make_keypoints(camera_id=cid, video_path=str(video)),
                          str(io.stage_paths(out_path, ids)["keypoints"][cid]))
    io.save_sync(make_sync(ids), str(io.stage_paths(out_path)["sync"]))
    out.write_text(json.dumps([{"t": 0.0, "landmarks": {}}]))
    out.with_suffix(".bvh").write_text("HIERARCHY\nMOTION\nFrames: 1\n")
    Path(f"{out.with_suffix('')}.metrics.json").write_text(json.dumps({"run": {"status": "done"}}))
    print(f"Saved 1 frames of 3D joints to {out_path}")


def gated_run(gate: threading.Event):
    """fake_run that blocks until the gate is set, so a take stays running."""
    def run(*args, **kw):
        gate.wait(timeout=10)
        fake_run(*args, **kw)
    return run


def failing_run(*args, **kw):
    raise SystemExit("only 3 frames with the performer standing upright, need 10")


@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    out = tmp_path / "output"
    monkeypatch.setattr(api, "OUTPUT_DIR", out)
    return out


@pytest.fixture
def ids(monkeypatch):
    """Predictable, increasing take ids so 'newest first' is testable."""
    counter = iter(range(1, 1000))
    monkeypatch.setattr(api, "new_take_id", lambda: f"20261016-{next(counter):06d}-abcd")


@pytest.fixture
def client(output_dir, ids, monkeypatch):
    monkeypatch.setattr(api, "run", fake_run)
    monkeypatch.setattr(api, "new_executor", lambda: ThreadExecutor())
    with TestClient(api.app) as c:
        yield c


def upload(client, cameras=("cam0", "cam1"), ext=".mp4", **fields):
    fields.setdefault("height_m", "1.75")
    files = [(cam, (f"{cam}{ext}", VIDEO, "video/mp4")) for cam in cameras]
    return client.post("/takes", files=files, data=fields)


def wait_for(client, take_id, statuses=("done", "failed"), timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        record = client.get(f"/takes/{take_id}").json()
        if record["status"] in statuses:
            return record
        time.sleep(0.02)
    raise AssertionError(f"take {take_id} never reached {statuses}: {record}")


# ---- upload parsing ------------------------------------------------------------------

def test_upload_creates_a_queued_take_with_the_videos_in_camera_order(client, output_dir):
    r = upload(client, ("cam1", "cam0", "cam2"), name="  First take ", project_id="proj-1")
    assert r.status_code == 202, r.text
    record = r.json()
    assert record["camera_count"] == 3 and record["height_m"] == 1.75
    assert record["name"] == "First take" and record["project_id"] == "proj-1"
    assert record["status"] in ("queued", "running", "done")
    folder = output_dir / record["id"]
    assert sorted(p.name for p in folder.glob("cam*")) == ["cam0.mp4", "cam1.mp4", "cam2.mp4"]
    assert (folder / "cam0.mp4").read_bytes() == VIDEO
    assert wait_for(client, record["id"])["status"] == "done"


def test_five_cameras_are_accepted(client):
    r = upload(client, tuple(f"cam{c}" for c in range(5)))
    assert r.status_code == 202
    assert r.json()["camera_count"] == 5


@pytest.mark.parametrize("cameras, hint", [
    (("cam0",), "at least 2"),
    (("cam0", "cam2"), "no gaps"),
    (("cam1", "cam2"), "no gaps"),
])
def test_too_few_or_gapped_cameras_are_rejected(client, output_dir, cameras, hint):
    r = upload(client, cameras)
    assert r.status_code == 422 and hint in r.json()["detail"]
    assert not any(output_dir.glob("2026*"))             # the folder was removed


def test_wrong_extension_and_unexpected_fields_are_rejected(client):
    assert upload(client, ext=".avi").status_code == 422
    r = client.post("/takes", files=[("video", ("x.mp4", VIDEO, "video/mp4"))], data={"height_m": "1.75"})
    assert r.status_code == 422 and "unexpected file field" in r.json()["detail"]
    r = upload(client, colour="red")
    assert r.status_code == 422 and "unexpected field" in r.json()["detail"]
    r = client.post("/takes", files=[("cam1", ("b.mp4", VIDEO, "video/mp4"))], data={"height_m": "1.75", "cam0": "text"})
    assert r.status_code == 422 and "must be a video file" in r.json()["detail"]


@pytest.mark.parametrize("height, hint", [
    (None, "required"), ("tall", "number"), ("0.5", "between"), ("3.0", "between"), ("nan", "between"),
])
def test_height_is_validated(client, height, hint):
    fields = {} if height is None else {"height_m": height}
    files = [(cam, (f"{cam}.mp4", VIDEO, "video/mp4")) for cam in ("cam0", "cam1")]
    r = client.post("/takes", files=files, data=fields)
    assert r.status_code == 422 and hint in r.json()["detail"]


def test_name_and_project_id_limits(client):
    assert upload(client, name="x" * 101).status_code == 422
    assert upload(client, project_id="has spaces").status_code == 422
    assert upload(client, name="", project_id="").json()["name"] is None


def test_non_multipart_body_is_rejected(client):
    r = client.post("/takes", json={"height_m": 1.75})
    assert r.status_code == 422 and "multipart" in r.json()["detail"]


def test_oversize_video_stops_the_upload_with_413(client, output_dir, monkeypatch):
    monkeypatch.setenv("MOCAP_MAX_UPLOAD_MB", str(1 / 1024 / 1024 * 64))   # 64 bytes
    r = upload(client)
    assert r.status_code == 413 and "larger than" in r.json()["detail"]
    assert not any(output_dir.glob("2026*"))


# ---- records, listing, results -------------------------------------------------------------

def test_unknown_and_malformed_ids_are_404(client):
    assert client.get("/takes/20261016-000099-abcd").status_code == 404
    assert client.get("/takes/not-an-id").status_code == 404
    assert client.get("/takes/../../etc").status_code == 404
    assert client.delete("/takes/20261016-000099-abcd").status_code == 404


def test_list_is_newest_first_and_filters_by_project(client):
    a = upload(client, project_id="p1").json()["id"]
    b = upload(client, project_id="p2").json()["id"]
    c = upload(client).json()["id"]
    assert [t["id"] for t in client.get("/takes").json()] == [c, b, a]
    assert [t["id"] for t in client.get("/takes", params={"project_id": "p1"}).json()] == [a]
    assert client.get("/takes", params={"project_id": "none"}).json() == []


def test_results_and_metrics_are_served_when_done(client):
    take_id = upload(client).json()["id"]
    record = wait_for(client, take_id)
    assert record["status"] == "done" and record["error"] is None and record["finished_at"]
    assert client.get(f"/takes/{take_id}/out3d.json").json() == [{"t": 0.0, "landmarks": {}}]
    assert client.get(f"/takes/{take_id}/out3d.bvh").text.startswith("HIERARCHY")
    assert client.get(f"/takes/{take_id}/metrics.json").json()["run"]["status"] == "done"


def test_keypoints_are_listed_and_served_per_camera(client):
    take_id = upload(client, ("cam0", "cam1")).json()["id"]
    assert client.get(f"/takes/{take_id}/keypoints.json").status_code in (409, 200)   # queued or already done
    wait_for(client, take_id)

    cameras = client.get(f"/takes/{take_id}/keypoints.json").json()["cameras"]
    assert [c["camera_id"] for c in cameras] == ["cam0", "cam1"]
    assert cameras[0] == {"camera_id": "cam0", "width": 1920, "height": 1080, "fps": 29.97, "frames": 12,
                          "clap_time_s": 1.0}
    assert cameras[1]["clap_time_s"] == 1.25

    kp = client.get(f"/takes/{take_id}/keypoints/cam1.json").json()
    assert kp["camera_id"] == "cam1" and kp["clap_time_s"] == 1.25
    assert kp["joints"] == JOINTS and kp["joints"][0] == "NOSE" and kp["joints"][-5:] == EXTRA_JOINTS
    assert len(kp["timestamps"]) == 12 and len(kp["points"]) == 12 and len(kp["points"][0]) == NUM_JOINTS
    assert kp["points"][3][5] is None and kp["confidence"][3][5] == 0.0     # the gap conftest plants
    assert isinstance(kp["points"][0][0], list) and len(kp["points"][0][0]) == 2

    assert client.get(f"/takes/{take_id}/keypoints/cam7.json").status_code == 404
    assert client.get(f"/takes/{take_id}/keypoints/camera.json").status_code == 404
    assert client.get("/takes/20261016-000099-abcd/keypoints.json").status_code == 404


def test_keypoints_saved_with_33_joints_are_served_with_33_names(client, output_dir):
    # takes processed before joints.EXTRA_JOINTS existed
    take_id = upload(client, ("cam0", "cam1")).json()["id"]
    wait_for(client, take_id)
    old = make_keypoints(camera_id="cam0")
    old.points, old.confidence = old.points[:, :33], old.confidence[:, :33]
    io.save_keypoints(old, str(output_dir / take_id / "out3d.keypoints.cam0.npz"))

    kp = client.get(f"/takes/{take_id}/keypoints/cam0.json").json()
    assert kp["joints"] == MEDIAPIPE_JOINTS and len(kp["points"][0]) == 33


def test_stage_is_parsed_from_the_pipelines_output(client, output_dir):
    take_id = upload(client).json()["id"]
    wait_for(client, take_id)
    log = (output_dir / take_id / "log.txt").read_text()
    assert "Detecting joints in" in log and "Saved 1 frames" in log
    # the last stage the LogWriter saw before "done" cleared it
    assert "writing" in log or client.get(f"/takes/{take_id}").json()["stage"] is None


def test_pipeline_failure_is_recorded_and_results_are_409(output_dir, ids, monkeypatch):
    monkeypatch.setattr(api, "run", failing_run)
    monkeypatch.setattr(api, "new_executor", lambda: ThreadExecutor())
    with TestClient(api.app) as client:
        take_id = upload(client).json()["id"]
        record = wait_for(client, take_id)
        assert record["status"] == "failed" and "standing upright" in record["error"]
        assert client.get(f"/takes/{take_id}/out3d.json").status_code == 409
        assert client.get(f"/takes/{take_id}/metrics.json").status_code == 404   # failed before writing one
        assert "FAILED" in (output_dir / take_id / "log.txt").read_text()


# ---- the queue ---------------------------------------------------------------------------

def test_takes_run_one_at_a_time_and_a_queued_take_can_be_cancelled(output_dir, ids, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(api, "run", gated_run(gate))
    monkeypatch.setattr(api, "new_executor", lambda: ThreadExecutor())
    with TestClient(api.app) as client:
        first = upload(client).json()["id"]
        second = upload(client).json()["id"]
        wait_for(client, first, statuses=("running",))
        assert client.get(f"/takes/{second}").json()["status"] == "queued"

        # running: refused. queued: cancelled and removed.
        assert client.delete(f"/takes/{first}").status_code == 409
        assert client.delete(f"/takes/{second}").status_code == 204
        assert client.get(f"/takes/{second}").status_code == 404
        assert not (output_dir / second).exists()

        gate.set()
        assert wait_for(client, first)["status"] == "done"
        assert client.delete(f"/takes/{first}").status_code == 204
        assert client.get("/takes").json() == []


def test_delete_many_reports_each_outcome(client):
    done = upload(client).json()["id"]
    wait_for(client, done)
    r = client.post("/takes/delete", json={"ids": [done, "20261016-000099-abcd", "junk"]})
    assert r.json() == {"results": {done: "deleted", "20261016-000099-abcd": "not_found", "junk": "not_found"}}


def test_a_dead_worker_pool_is_replaced(output_dir, ids, monkeypatch):
    executors = []

    def new_executor():
        executors.append(ThreadExecutor(break_first=len(executors) == 0))
        return executors[-1]

    monkeypatch.setattr(api, "run", fake_run)
    monkeypatch.setattr(api, "new_executor", new_executor)
    with TestClient(api.app) as client:
        take_id = upload(client).json()["id"]
        assert wait_for(client, take_id)["status"] == "done"
    assert len(executors) == 2


# ---- restart recovery ---------------------------------------------------------------------

def test_takes_left_running_by_a_previous_server_are_marked_failed(output_dir, ids, monkeypatch):
    monkeypatch.setattr(api, "new_executor", lambda: ThreadExecutor())
    for take_id, status in (("20261016-000001-abcd", "running"), ("20261016-000002-abcd", "queued"),
                            ("20261016-000003-abcd", "done")):
        folder = output_dir / take_id
        folder.mkdir(parents=True)
        api.write_status(folder, {"id": take_id, "status": status, "error": None, "finished_at": None})
    (output_dir / "not-a-take").mkdir()

    with TestClient(api.app) as client:
        records = {t["id"]: t for t in client.get("/takes").json()}
    assert records["20261016-000001-abcd"]["status"] == "failed"
    assert "interrupted" in records["20261016-000001-abcd"]["error"]
    assert records["20261016-000002-abcd"]["status"] == "failed"
    assert records["20261016-000003-abcd"]["status"] == "done"
    assert records["20261016-000003-abcd"]["project_id"] is None     # old records get the field


def test_status_file_is_written_atomically(output_dir):
    folder = output_dir / "20261016-000001-abcd"
    folder.mkdir(parents=True)
    api.write_status(folder, {"id": "x", "status": "queued"})
    assert [p.name for p in folder.iterdir()] == ["status.json"]     # no temp file left behind
    api.update_status(folder, status="running")
    assert api.read_status(folder)["status"] == "running"
    (folder / "status.json").write_text("{not json")
    assert api.read_status(folder) is None
