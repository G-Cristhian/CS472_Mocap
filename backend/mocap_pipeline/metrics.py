"""
Quality numbers for one run, written next to the output as <out>.metrics.json,
and a copy of everything printed, written as <out>.log.

There is no ground truth in the field, so these are precision and
self-consistency measures, the same ones the literature uses when truth is
absent: reprojection error (Zhang 2000, DOI 10.1109/34.888718; Triggs et al.
1999, DOI 10.1007/3-540-44480-7_21) and limb-length variability (Karashchuk et
al. 2021, DOI 10.1016/j.celrep.2021.109730). Against the synthetic scene,
tests/evaluate_synthetic.py adds MPJPE (Ionescu et al. 2014, DOI
10.1109/TPAMI.2013.248), which needs the truth.

How to use, from any stage:

    from .. import metrics
    metrics.record("triangulate.views_dropped", int(n))

Keys are "<stage>.<name>", dotted, and become nested objects in the JSON.
Recording when no run is open is a no-op, so the stages work unchanged when
called on their own (tests, notebooks). run_pipeline opens the run with
start() and closes it with finish(); finish() writes the files.

Stage timing: time("stage") is a context manager that records
"timing.<stage>_s". stage1 per-camera numbers come from the Keypoints2D
arrays, so they are available on --resume too.
"""
from __future__ import annotations

import json
import sys
import time as _time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np

from .joints import MEDIAPIPE_JOINTS

_run: dict | None = None
_paths: dict | None = None
_tee = None


# ---- recording ---------------------------------------------------------------

def _clean(value):
    """JSON-safe: numpy scalars and arrays become Python numbers and lists, NaN becomes null."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_clean(v) for v in np.asarray(value).tolist()] if isinstance(value, np.ndarray) else [_clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.integer, int, bool, str)) or value is None:
        return value.item() if isinstance(value, np.integer) else value
    return str(value)


def record(key: str, value) -> None:
    """Store one number (or dict/list of numbers) under a dotted key. No-op outside a run."""
    if _run is None:
        return
    node = _run
    *parents, leaf = key.split(".")
    for p in parents:
        node = node.setdefault(p, {})
        if not isinstance(node, dict):
            raise ValueError(f"metrics key {key!r} crosses a value")
    node[leaf] = _clean(value)


def active() -> bool:
    return _run is not None


@contextmanager
def time(stage: str):
    """Records timing.<stage>_s for the block."""
    t0 = _time.perf_counter()
    try:
        yield
    finally:
        record(f"timing.{stage}_s", round(_time.perf_counter() - t0, 3))


# ---- per-stage helpers (pure functions over the schemas, so they also run on --resume) -------

def keypoints_summary(kp) -> dict:
    """Stage 1 quality for one camera from its Keypoints2D."""
    conf = np.asarray(kp.confidence, dtype=float)
    seen = conf > 0
    no_person = ~seen.any(axis=1)
    return {
        "frames": int(len(conf)),
        "fps_nominal": float(kp.fps),
        "no_person_fraction": float(no_person.mean()) if len(conf) else None,
        "mean_confidence": float(conf[seen].mean()) if seen.any() else None,
        "mean_confidence_per_joint": {n: (float(conf[:, j][seen[:, j]].mean()) if seen[:, j].any() else None)
                                      for j, n in enumerate(MEDIAPIPE_JOINTS)},
    }


def pose_summary(pose) -> dict:
    """Stage 2c coverage from a Pose3D: how much of the take has 3D for each joint."""
    pts = np.asarray(pose.points)
    missing = np.isnan(pts).any(axis=2)                       # (F, J)
    return {
        "frames": int(len(pts)),
        "missing_fraction": float(missing.mean()) if pts.size else None,
        "missing_fraction_per_joint": {n: float(missing[:, j].mean()) for j, n in enumerate(MEDIAPIPE_JOINTS)},
        "mean_views_per_joint": float(np.asarray(pose.num_views)[~missing].mean()) if (~missing).any() else None,
    }


def bone_length_summary(rig_positions, rig_joints, rig_parents) -> dict:
    """
    Stage 3 precision: for each bone, the standard deviation of its length over
    the take in metres, and the fraction of its median. A rigid body has zero;
    what is left is detection noise plus the stage 2 geometry. The rig fixes
    bone lengths to the median, so this is also how much the BVH bends the
    data (Karashchuk et al. 2021 use the same measure).
    """
    index = {n: i for i, n in enumerate(rig_joints)}
    out = {}
    for name, parent in rig_parents.items():
        if parent is None:
            continue
        d = np.linalg.norm(rig_positions[:, index[name]] - rig_positions[:, index[parent]], axis=1)
        d = d[np.isfinite(d)]
        if len(d):
            med = float(np.median(d))
            out[name] = {"median_m": med, "std_m": float(np.std(d)),
                         "std_fraction": float(np.std(d) / med) if med > 0 else None}
    stds = [b["std_m"] for b in out.values()]
    return {"per_bone": out, "mean_std_m": float(np.mean(stds)) if stds else None,
            "max_std_m": float(np.max(stds)) if stds else None}


# ---- the run -------------------------------------------------------------------

class _Tee:
    """Copies everything printed to the log file, each line stamped with the time."""

    def __init__(self, inner, path: Path):
        self.inner = inner
        self.log = open(path, "a", encoding="utf-8")
        self.partial = ""

    def write(self, text: str) -> int:
        n = self.inner.write(text)
        self.partial += text
        *lines, self.partial = self.partial.split("\n")
        for line in lines:
            self.log.write(f"{datetime.now():%H:%M:%S} {line}\n")
        self.log.flush()
        return n

    def flush(self) -> None:
        self.inner.flush()
        self.log.flush()

    def close(self) -> None:
        if self.partial:
            self.log.write(f"{datetime.now():%H:%M:%S} {self.partial}\n")
            self.partial = ""
        self.log.close()

    def __getattr__(self, name):
        return getattr(self.inner, name)


def paths_for(out_path: str) -> dict:
    stem = Path(out_path).with_suffix("")
    return {"metrics": Path(f"{stem}.metrics.json"), "log": Path(f"{stem}.log")}


def start(out_path: str, **header) -> None:
    """Open a run: reset the numbers, start copying stdout to <out>.log. header values are recorded under run."""
    global _run, _paths, _tee
    finish_quietly()
    _paths = paths_for(out_path)
    _paths["log"].parent.mkdir(parents=True, exist_ok=True)
    _run = {"run": {"started": datetime.now().astimezone().isoformat(timespec="seconds"), **_clean(header)}}
    _tee = _Tee(sys.stdout, _paths["log"])
    sys.stdout = _tee


def finish(status: str = "done", error: str | None = None) -> Path | None:
    """Close the run and write <out>.metrics.json. Returns its path."""
    global _run, _paths, _tee
    if _run is None:
        return None
    _run["run"]["finished"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _run["run"]["status"] = status
    if error:
        _run["run"]["error"] = error
    path = _paths["metrics"]
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(_run, fp, indent=2)
    if _tee is not None:
        sys.stdout = _tee.inner
        _tee.close()
    _run, _paths, _tee = None, None, None
    return path


def finish_quietly() -> None:
    """Drop an open run without writing (a new start() while one is open)."""
    global _run, _paths, _tee
    if _tee is not None:
        sys.stdout = _tee.inner
        _tee.close()
    _run, _paths, _tee = None, None, None


def load(out_path: str) -> dict:
    with open(paths_for(out_path)["metrics"], encoding="utf-8") as fp:
        return json.load(fp)
