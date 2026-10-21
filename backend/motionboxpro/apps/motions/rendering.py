"""
Renders one motion version: runs the mocap pipeline (backend/mocap_pipeline) on the motion's
recordings and keeps every output in the MotionVersion row. The pipeline writes its files to a
folder it is given; here that folder is temporary, and it is deleted once the outputs are saved.

The render runs in its own process, so the web server stays responsive and the pipeline's
memory is given back when it finishes. The process is a fresh interpreter, which is why it
sets Django up itself. Keep this module free of heavy imports: the pipeline is imported inside
the render, not when Django loads the app.
"""

from __future__ import annotations

import contextlib
import io
import json
import multiprocessing
import tempfile
import traceback
from pathlib import Path


def start_render(version_pk: int) -> None:
    """Starts the render in a new process and returns at once. The version's status shows how it goes."""
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=render_version, args=(version_pk,), name=f"render-version-{version_pk}")
    process.start()


def render_version(version_pk: int) -> None:
    """Entry point of the render process: runs the pipeline and saves the outputs on the version."""
    import django

    django.setup()

    from motionboxpro.apps.motions.models import MotionVersion

    version = MotionVersion.objects.get(pk=version_pk)
    version.status = MotionVersion.Status.RUNNING
    version.error = ""
    version.save(update_fields=["status", "error", "updated_at"])

    log = io.StringIO()
    try:
        with tempfile.TemporaryDirectory(prefix="motion-version-") as folder:
            _run_pipeline(version, Path(folder), log)
            _keep_outputs(version, Path(folder))
        version.log = log.getvalue()
        _finish(version, MotionVersion.Status.DONE)
    except SystemExit as error:
        version.log = log.getvalue()
        _finish(version, MotionVersion.Status.FAILED, f"The pipeline stopped: {error.code}")
    except Exception as error:
        log.write(traceback.format_exc())
        version.log = log.getvalue()
        _finish(version, MotionVersion.Status.FAILED, str(error))


def _run_pipeline(version, folder: Path, log: io.StringIO) -> None:
    # imported here: the pipeline pulls in mediapipe, which only a render needs
    from mocap_pipeline.run_pipeline import run

    links = version.motion.motion_recordings.select_related("recording").order_by("camera_slot")
    # camera order is the order of the links: slot 0 is the reference camera
    videos = [link.recording.video.path for link in links]

    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        run(
            video_paths=videos,
            out_path=str(folder / "out3d.json"),
            performer_height_m=version.height_m,
            calibration_path=str(folder / "calibration.json"),
            recalibrate=True,
            detector=version.pose_model,
            bvh=True,
        )


def _keep_outputs(version, folder: Path) -> None:
    """Reads what the pipeline wrote into the version's fields. Missing files raise, which fails the render."""
    frames = json.loads((folder / "out3d.json").read_text())
    version.out3d = frames
    version.bvh = (folder / "out3d.bvh").read_text()
    version.calibration = json.loads((folder / "calibration.json").read_text())

    metrics = folder / "out3d.metrics.json"
    version.metrics = json.loads(metrics.read_text()) if metrics.exists() else None

    version.frame_count = len(frames)
    if len(frames) > 1:
        duration = frames[-1]["t"] - frames[0]["t"]
        version.duration_s = duration
        version.fps = (len(frames) - 1) / duration if duration > 0 else None


def _finish(version, status: str, error: str = "") -> None:
    from django.utils import timezone

    version.status = status
    version.error = error
    version.finished_at = timezone.now()
    version.save()
