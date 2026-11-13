"""
Renders one motion version: runs the mocap pipeline (backend/mocap_pipeline) on the motion's
recordings and keeps every output in the MotionVersion row. The pipeline writes its files to a
folder it is given; here that folder is temporary, and it is deleted once the outputs are saved.

The render runs in its own process, so the web server stays responsive and the pipeline's
memory is given back when it finishes. The process is a fresh interpreter, which is why it
sets Django up itself. Keep this module free of heavy imports: the pipeline is imported inside
the render, not when Django loads the app.

While it runs, the render process writes a heartbeat on its version. If the process dies before
it can save a result (killed, out of memory, a native crash, the machine sleeping or rebooting),
the heartbeat stops, and fail_stale_renders marks the version failed so the motion can render again.
"""

from __future__ import annotations

import contextlib
import io
import json
import multiprocessing
import tempfile
import threading
import traceback
from pathlib import Path

# how often a running render writes its heartbeat
HEARTBEAT_SECONDS = 10
# a queued or running render with no sign of life for this long counts as dead. Matches the
# frontend's one-minute lost-connection window
STALE_AFTER_SECONDS = 60


def start_render(version_pk: int) -> None:
    """Starts the render in a new process and returns at once. The version's status shows how it goes."""
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=render_version, args=(version_pk,), name=f"render-version-{version_pk}")
    process.start()


def render_version(version_pk: int) -> None:
    """Entry point of the render process: runs the pipeline and saves the outputs on the version."""
    import django

    django.setup()

    from django.utils import timezone

    from motionboxpro.apps.motions.models import MotionVersion

    version = MotionVersion.objects.get(pk=version_pk)
    version.status = MotionVersion.Status.RUNNING
    version.error = ""
    version.started_at = version.heartbeat_at = timezone.now()
    version.save(update_fields=["status", "error", "started_at", "heartbeat_at", "updated_at"])

    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_beat, args=(version_pk, stop), name=f"render-heartbeat-{version_pk}", daemon=True
    )
    heartbeat.start()

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
    finally:
        stop.set()
        heartbeat.join()


def _beat(version_pk: int, stop: threading.Event) -> None:
    """The heartbeat thread of the render process: stamps the version every HEARTBEAT_SECONDS until stopped."""
    from django.db import connection
    from django.utils import timezone

    from motionboxpro.apps.motions.models import MotionVersion

    try:
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                # update(), never save(): the beat must not write over anything the render saves
                MotionVersion.objects.filter(pk=version_pk).update(heartbeat_at=timezone.now())
            except Exception:
                # a missed beat (e.g. the database was briefly unreachable) is retried on the next one
                pass
    finally:
        # the thread has its own database connection; close it rather than leave it to the process exit
        connection.close()


def mark_failed_if_active(version_pk: int, message: str) -> None:
    """
    Marks the version failed, but only while it is still queued or running. One conditional
    update, never save(), so a render that has already finished is never overwritten.
    """
    from django.utils import timezone

    from motionboxpro.apps.motions.models import MotionVersion

    MotionVersion.objects.filter(
        pk=version_pk,
        status__in=[MotionVersion.Status.QUEUED, MotionVersion.Status.RUNNING],
    ).update(status=MotionVersion.Status.FAILED, error=message, finished_at=timezone.now())


def fail_stale_renders(queryset) -> None:
    """
    Marks failed every queued or running version in the queryset that has shown no sign of
    life for STALE_AFTER_SECONDS: its last heartbeat, or its creation if the render process
    never picked it up. Pass only a scoped queryset, e.g. one motion's or one user's versions.
    """
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    from motionboxpro.apps.motions.models import MotionVersion

    cutoff = timezone.now() - timedelta(seconds=STALE_AFTER_SECONDS)
    stale = queryset.filter(
        Q(heartbeat_at__lt=cutoff) | Q(heartbeat_at__isnull=True, created_at__lt=cutoff),
        status__in=[MotionVersion.Status.QUEUED, MotionVersion.Status.RUNNING],
    )
    for pk in stale.values_list("pk", flat=True):
        mark_failed_if_active(pk, "The render stopped unexpectedly (no sign of life for over a minute).")


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
    # Unconditional on purpose: the render's own result is final, even over a "failed" that
    # fail_stale_renders wrote while it seemed dead. A render that resumes after the machine
    # slept can still end as done.
    version.save()
