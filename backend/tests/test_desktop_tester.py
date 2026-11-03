"""
The desktop tester (desktop/, the "Mocap backend tester" window) against the
real backend. The window has two contracts with the pipeline: it spawns
`python -m mocap_pipeline.run_pipeline` the way processing-a-take.md does, and
it turns the lines the run prints into a progress bar, a result and an error
message. Both are checked here with the app's own compiled code, driven by
desktop/test/harness.cjs:

- replay tests run run_pipeline.run() in this process (stage 1 replaced by
  the synthetic scene's observations, as test_synthetic_pipeline does) and
  feed every printed line through the app's ProgressTracker. A renamed print
  in run_pipeline.py that would freeze the bar fails here, not at a session.
- subprocess tests let the app's runPipeline() spawn the real pipeline with
  the backend's Python on synthetic videos. MediaPipe sees no person in them,
  so the run ends at calibration with the documented message; that exercises
  detection progress, the clap search, stderr handling and the cancel button.

Needs Node and `npm install` in desktop/; skipped otherwise. Marked
`desktop`, so `pytest -m "not desktop"` leaves them out.
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from mocap_pipeline import run_pipeline
from mocap_pipeline.stage1_keypoints import detect
from tests.synthetic_scene import PERFORMER_HEIGHT_M, Noise, Routine, Scene

pytestmark = pytest.mark.desktop

REPO = Path(__file__).resolve().parents[2]
DESKTOP = REPO / "desktop"
NODE = shutil.which("node")
SHORT = Routine(stand_s=2.0, walk_s=6.0, perform_s=3.0)
REALISTIC = Noise(pixel_sigma=1.5, dropout=0.02, outlier=0.005)


# ---- the app's code, compiled once -------------------------------------------------------

@pytest.fixture(scope="session")
def harness() -> Path:
    """desktop/test/harness.cjs with dist/main freshly compiled from desktop/src."""
    if NODE is None:
        pytest.skip("node is not installed")
    tsc = DESKTOP / "node_modules" / "typescript" / "bin" / "tsc"
    if not tsc.exists():
        pytest.skip("desktop/node_modules is missing: run `npm install` in desktop/")
    build = subprocess.run([NODE, str(tsc), "-p", "tsconfig.main.json"], cwd=DESKTOP, capture_output=True, text=True)
    assert build.returncode == 0, f"tsc failed:\n{build.stdout}{build.stderr}"
    return DESKTOP / "test" / "harness.cjs"


def replay(harness, videos, lines, exit_code=0) -> dict:
    """The app's progress events and result for these printed lines. lines: (text, from_stderr) pairs."""
    doc = {"videos": [str(v) for v in videos], "lines": [{"text": t, "stderr": s} for t, s in lines],
           "exitCode": exit_code}
    proc = subprocess.run([NODE, str(harness), "replay"], input=json.dumps(doc), capture_output=True, text=True,
                          cwd=DESKTOP, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def run_app(harness, options: dict, cancel_on: str | None = None) -> dict:
    """runPipeline() as the window calls it: the log lines, progress events, result and the Python it chose."""
    options_path = Path(options["outDir"]).parent / "options.json"
    options_path.write_text(json.dumps(options))
    cmd = [NODE, str(harness), "run", str(options_path)] + (["--cancel-on", cancel_on] if cancel_on else [])
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=DESKTOP, timeout=180)
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(proc.stdout)
    if any("No module named" in line or "Could not start" in line for line in doc["log"]):
        pytest.skip(f"{doc['python']} cannot run the pipeline:\n" + "\n".join(doc["log"]))
    return doc


def write_stand_in_video(path: str) -> None:
    Path(path).write_bytes(b"stand-in for a phone video")


def stdout_lines(capsys) -> list[tuple[str, bool]]:
    return [(line, False) for line in capsys.readouterr().out.splitlines()]


def assert_monotonic(progress: list[dict]) -> None:
    fractions = [p["fraction"] for p in progress]
    assert fractions == sorted(fractions), fractions
    assert all(0 <= f <= 1 for f in fractions)


def first_appearances(progress: list[dict]) -> list[str]:
    seen = []
    for p in progress:
        if p["stage"] not in seen:
            seen.append(p["stage"])
    return seen


# ---- replay: the lines a run prints, through the app's tracker ------------------------------

@pytest.fixture
def scene_take(tmp_path, monkeypatch):
    """
    Three stand-in phone videos whose stage 1 result is the synthetic scene's
    observation of them, with detect.py's progress line printed as it would be
    under MOCAP_PROGRESS. Returns (video paths, run) where run(**kw) is
    run_pipeline.run on them with the output under tmp_path/output.
    """
    scene = Scene(routine=SHORT, fps=(60.0, 30.0, 30.0), clap_s=(1.0, 0.85, 2.3), noise=REALISTIC)
    recorded = {k.video_path: k for k in scene.recorded_keypoints(str(tmp_path))}
    for path in recorded:
        write_stand_in_video(path)

    def fake_detect(video_path, model_path, detector="mediapipe"):
        print(f"progress: detect {video_path} 30/60", flush=True)       # detect.py's line, every 30 frames
        return recorded[str(video_path)]

    monkeypatch.setattr(detect, "detect_video", fake_detect)
    videos = list(recorded)
    out = tmp_path / "output" / "out3d.json"

    def run(**kw):
        kw.setdefault("clap_times", scene.clap_times())
        kw.setdefault("jobs", 1)                                        # the fake runs in this process
        run_pipeline.run(videos, str(out), performer_height_m=PERFORMER_HEIGHT_M, model_path="unused",
                         camera=["webcam"] * 3, fov=[65.0] * 3,
                         calibration_path=str(tmp_path / "output" / "calibration.json"), **kw)
        return out

    return videos, run


def test_the_bar_follows_a_full_run_to_done_with_the_result_files(harness, scene_take, capsys):
    videos, run = scene_take
    out = run()
    doc = replay(harness, videos, stdout_lines(capsys))

    progress, result = doc["progress"], doc["result"]
    assert first_appearances(progress) == ["detecting", "calibrating", "triangulating", "writing", "done"]
    assert_monotonic(progress)
    details = [p["detail"] for p in progress]
    for video in videos:
        name = Path(video).name
        assert f"Detecting joints in {name}" in details
        assert f"Detecting joints in {name}, frame 30 of 60" in details
        assert f"Detected joints in {name}" in details
    assert progress[-1]["stage"] == "done" and progress[-1]["fraction"] == 1
    assert progress[-1]["detail"] == "Saved out3d.bvh"
    assert [v["state"] for v in progress[-1]["videos"]] == ["done"] * 3

    assert result["ok"] is True and result["exitCode"] == 0 and "error" not in result
    assert result["jsonPath"] == str(out)
    assert result["bvhPath"] == str(out.with_suffix(".bvh"))
    assert result["metricsPath"] == str(out.parent / "out3d.metrics.json")
    for key in ("jsonPath", "bvhPath", "metricsPath"):
        assert Path(result[key]).exists(), key


def test_a_resumed_run_is_followed_through_its_reuse_lines(harness, scene_take, capsys):
    videos, run = scene_take
    run()
    capsys.readouterr()
    out = run(resume=True, clap_times=None)          # saved joints, clap times, calibration and 3D joints
    doc = replay(harness, videos, stdout_lines(capsys))

    details = [p["detail"] for p in doc["progress"]]
    assert all(f"Reusing saved joints for {Path(v).name}" in details for v in videos)
    assert "Synchronised from the saved clap times" in details
    assert "Reusing the saved 3D joints" in details
    assert_monotonic(doc["progress"])
    assert doc["progress"][-1]["stage"] == "done" and doc["progress"][-1]["fraction"] == 1
    assert [v["state"] for v in doc["progress"][-1]["videos"]] == ["reused"] * 3
    assert doc["result"]["ok"] is True and doc["result"]["bvhPath"] == str(out.with_suffix(".bvh"))


def test_a_failed_calibration_shows_the_pipelines_own_message(harness, tmp_path, monkeypatch, capsys):
    """Standing still only: run_pipeline raises SystemExit with the two-line message filming.md lists."""
    scene = Scene(routine=Routine(stand_s=4.0, walk_s=0.0, perform_s=0.0), noise=Noise(pixel_sigma=1.0))
    recorded = {k.video_path: k for k in scene.recorded_keypoints(str(tmp_path))}
    for path in recorded:
        write_stand_in_video(path)
    monkeypatch.setattr(detect, "detect_video", lambda video_path, model_path, detector="mediapipe": recorded[str(video_path)])
    videos = list(recorded)

    with pytest.raises(SystemExit) as e:
        run_pipeline.run(videos, str(tmp_path / "output" / "out3d.json"), performer_height_m=PERFORMER_HEIGHT_M,
                         model_path="unused", camera=["webcam"] * 3, fov=[65.0] * 3, clap_times=scene.clap_times(),
                         calibration_path=str(tmp_path / "output" / "calibration.json"), jobs=1)
    # what the child process prints: stdout so far, then Python prints the SystemExit message on stderr
    lines = stdout_lines(capsys) + [(line, True) for line in str(e.value).splitlines()]
    doc = replay(harness, videos, lines, exit_code=1)

    assert doc["progress"][-1]["stage"] == "calibrating"
    assert doc["progress"][-1]["detail"].startswith("Calibration from the performer failed")
    assert "move around more" in doc["progress"][-1]["detail"]
    assert doc["result"]["ok"] is False and doc["result"]["exitCode"] == 1
    assert "--charuco-videos" in doc["result"]["error"]
    assert "bvhPath" not in doc["result"]


# ---- subprocess: the app spawns the real pipeline --------------------------------------------

def make_take(tmp_path, seconds: float) -> dict:
    """Two synthetic phone videos (a moving rectangle, a clap each) and the window's RunOptions for them."""
    pytest.importorskip("av")
    from tests.synthetic_video import write_video

    take = tmp_path / "take"
    take.mkdir()
    write_video(take / "cam0.mp4", fps=30, seconds=seconds, clap_at=0.40, seed=0)
    write_video(take / "cam1.mp4", fps=30, seconds=seconds, clap_at=0.25, seed=1)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    return {"videos": [str(take / "cam0.mp4"), str(take / "cam1.mp4")], "heightM": 1.75, "outDir": str(out_dir),
            "detector": "mediapipe", "smoother": "savgol", "fov": 65, "clapThreshold": 1, "clapTimes": None,
            "jobs": 0, "recalibrate": True, "resume": False}


@pytest.fixture
def synthetic_take(tmp_path):
    """A short take: 45 frames per camera, about a second of detection each."""
    return make_take(tmp_path, seconds=1.5)


def test_the_app_runs_the_real_pipeline_and_reports_its_failure(harness, synthetic_take):
    doc = run_app(harness, synthetic_take)
    out_dir = Path(synthetic_take["outDir"])
    log, progress, result = doc["log"], doc["progress"], doc["result"]

    # the command line, shown first in the log
    assert log[0].startswith("$ ") and " -u -m mocap_pipeline.run_pipeline " in log[0]
    assert f"--out {out_dir / 'out3d.json'}" in log[0] and f"--calibration {out_dir / 'calibration.json'}" in log[0]
    assert "--height-m 1.75" in log[0] and "--detector mediapipe" in log[0] and "--smoother savgol" in log[0]
    assert "--fov 65" in log[0] and "--jobs 0" in log[0]
    assert "--clap-threshold" not in log[0] and "--sync" not in log[0]        # the defaults are left out
    assert log[0].endswith("--recalibrate") and "--resume" not in log[0]
    assert "Cameras: cam0 webcam, cam1 webcam" in log

    # detection progress for each camera (MOCAP_PROGRESS is set by the app), then the clap, then the message
    details = [p["detail"] for p in progress]
    for cam in ("cam0.mp4", "cam1.mp4"):
        assert f"Detecting joints in {cam}" in details
        assert any(re.fullmatch(rf"Detecting joints in {cam}, frame 30 of \d+", d) for d in details), details
        assert f"Detected joints in {cam}" in details
    assert_monotonic(progress)
    # the per-video lines under the bar: both detected, with the seconds each took
    assert [v["state"] for v in progress[-1]["videos"]] == ["done", "done"]
    assert all(re.fullmatch(r"\d+ s", v["detail"]) for v in progress[-1]["videos"]), progress[-1]["videos"]
    assert first_appearances(progress) == ["detecting", "calibrating"]
    assert any(d.startswith("Synchronised: cam0 ") for d in details)
    assert progress[-1]["detail"].startswith("Calibration from the performer failed")
    assert progress[-1]["fraction"] < 1

    assert result["ok"] is False and result["exitCode"] == 1
    assert "--charuco-videos cam0_board.mp4 cam1_board.mp4" in result["error"]
    assert "bvhPath" not in result

    # the output folder holds what a terminal run leaves behind, so --resume can pick it up
    names = sorted(p.name for p in out_dir.iterdir())
    assert names == ["out3d.keypoints.cam0.npz", "out3d.keypoints.cam1.npz", "out3d.log", "out3d.metrics.json",
                     "out3d.sync.json"]
    assert json.loads((out_dir / "out3d.metrics.json").read_text())["run"]["status"] == "failed"
    assert "Clap at cam0" in (out_dir / "out3d.log").read_text(encoding="utf-8")


def test_cancel_before_detection_starts_kills_the_pipeline(harness, synthetic_take):
    doc = run_app(harness, synthetic_take, cancel_on="Detecting joints in")
    out_dir = Path(synthetic_take["outDir"])

    assert doc["result"]["ok"] is False and doc["result"]["error"] == "Cancelled"
    assert not (out_dir / "out3d.sync.json").exists()        # killed during detection, before the clap search
    assert not (out_dir / "out3d.json").exists()


def test_cancel_during_detection_stops_the_worker_processes(harness, tmp_path):
    """
    Stage 1 detects the videos in worker processes (--jobs). Cancel has to stop
    them too: a worker left running keeps the output pipes open, so the window
    would wait for a result that never comes, and it would still write its
    joints file. The take is long enough that a surviving worker would be
    caught: cancelled at frame 30 of 180, it would need several more seconds.
    """
    options = make_take(tmp_path, seconds=6.0)
    doc = run_app(harness, options, cancel_on="progress: detect")      # a worker is a sixth of the way through
    out_dir = Path(options["outDir"])
    assert doc["result"]["ok"] is False and doc["result"]["error"] == "Cancelled"
    assert any("Detecting 2 videos at once" in line or "Detecting joints in" in line for line in doc["log"])

    time.sleep(6)                                                     # a surviving worker would be done by now
    assert not list(out_dir.glob("out3d.keypoints.*.npz")), sorted(p.name for p in out_dir.iterdir())
    assert not (out_dir / "out3d.sync.json").exists()


def test_the_app_uses_the_backend_venv_when_there_is_one(harness, synthetic_take):
    venv = [p for p in (REPO / "backend" / ".venv" / "Scripts" / "python.exe", REPO / "backend" / ".venv" / "bin" / "python")
            if p.exists()]
    if not venv:
        pytest.skip("no backend/.venv on this machine")
    doc = run_app(harness, synthetic_take, cancel_on="Cameras:")
    assert os.path.normcase(doc["python"]) == os.path.normcase(str(venv[0]))
    assert doc["log"][0].startswith(f"$ {venv[0]} ")
