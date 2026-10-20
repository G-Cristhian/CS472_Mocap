# Copied from: legacy/multicam_3d/smooth.py (fill_gaps, smooth), filled into the
# mocap_pipeline/stage2_reconstruct/smooth.py placeholder (now taking and returning Pose3D).
"""
Stage 2c, clean-up: fill short gaps and remove jitter.

Input : raw Pose3D.  Output: cleaned Pose3D, same shape.
"""
from __future__ import annotations

import numpy as np

from .. import config, metrics
from ..schemas import Pose3D


def _runs(mask):
    """(start, end) of every run of True in a 1D mask, end exclusive."""
    starts = np.flatnonzero(mask & ~np.r_[False, mask[:-1]])
    ends = np.flatnonzero(mask & ~np.r_[mask[1:], False]) + 1
    return zip(starts, ends)


def fill_gaps(pose: Pose3D) -> Pose3D:
    """
    Per joint and axis, interpolate runs of NaN no longer than
    config.MAX_GAP_FILL_FRAMES that have data on both sides. Longer gaps stay
    NaN and are reported. Filled joints keep num_views = 0, so they can be
    told apart from measured ones.
    """
    p3ds = pose.points
    out = p3ds.copy()
    frames = np.arange(len(p3ds))
    long_gaps = 0
    filled = 0

    for j in range(p3ds.shape[1]):
        missing = np.isnan(p3ds[:, j]).any(axis=1)
        if missing.all() or not missing.any():
            continue
        known = ~missing
        for s, e in _runs(missing):
            if s == 0 or e == len(p3ds):
                continue
            if e - s > config.MAX_GAP_FILL_FRAMES:
                long_gaps += 1
                continue
            filled += 1
            for axis in range(3):
                out[s:e, j, axis] = np.interp(frames[s:e], frames[known], p3ds[known, j, axis])

    metrics.record("smooth.gaps", {"filled": filled, "left_missing": long_gaps})
    if long_gaps:
        print(f"{long_gaps} gaps longer than {config.MAX_GAP_FILL_FRAMES} frames left missing")
    return Pose3D(fps=pose.fps, points=out, num_views=pose.num_views.copy())


SMOOTHERS = ("savgol", "butterworth")


def _savgol(fps: float):
    """
    Savitzky-Golay: fit a polynomial of config.SMOOTH_POLYORDER through each
    window of config.SMOOTH_WINDOW_FRAMES points and keep the centre value.
    The window is small so fast motion such as a punch survives. Returns
    (filter over one continuous run, shortest run it can take, settings).
    """
    from scipy.signal import savgol_filter

    window, order = config.SMOOTH_WINDOW_FRAMES, config.SMOOTH_POLYORDER
    return (lambda run: savgol_filter(run, window, order, axis=0), window,
            {"window_frames": window, "polyorder": order})


def _butterworth(fps: float):
    """
    Butterworth low-pass of config.BUTTER_ORDER at config.BUTTER_CUTOFF_HZ,
    run forward and backward (sosfiltfilt) so the result has no lag. The
    cutoff must sit below half the frame rate (Nyquist). A run must be longer
    than the filter's padding, three times its length, to be filtered.
    """
    from scipy.signal import butter, sosfiltfilt

    cutoff, order = config.BUTTER_CUTOFF_HZ, config.BUTTER_ORDER
    nyquist = fps / 2.0
    if not 0 < cutoff < nyquist:
        raise ValueError(f"BUTTER_CUTOFF_HZ = {cutoff} must be between 0 and half the frame rate ({nyquist:g} Hz at {fps:g} fps)")
    sos = butter(order, cutoff / nyquist, btype="low", output="sos")
    padlen = 3 * (2 * len(sos) + 1)
    return (lambda run: sosfiltfilt(sos, run, axis=0, padlen=padlen), padlen + 1,
            {"cutoff_hz": cutoff, "order_per_pass": order})


def smooth(pose: Pose3D, method: str | None = None) -> Pose3D:
    """
    Low-pass each joint trajectory. method is "savgol" (Savitzky-Golay, the
    default from config.SMOOTHER) or "butterworth" (zero-phase Butterworth);
    both are kept so they can be compared on the same take. Each continuous
    run is filtered on its own so NaN gaps don't spread; runs too short for
    the filter are left as they are.
    """
    method = method or config.SMOOTHER
    if method not in SMOOTHERS:
        raise ValueError(f"smoother must be one of {SMOOTHERS}, got {method!r}")
    apply, min_run, settings = (_savgol if method == "savgol" else _butterworth)(pose.fps)
    metrics.record("smooth.method", method)
    metrics.record("smooth.settings", settings)

    p3ds = pose.points
    out = p3ds.copy()
    skipped = 0

    for j in range(p3ds.shape[1]):
        present = ~np.isnan(p3ds[:, j]).any(axis=1)
        for s, e in _runs(present):
            if e - s >= min_run:
                out[s:e, j] = apply(p3ds[s:e, j])
            else:
                skipped += 1

    metrics.record("smooth.runs_too_short", skipped)
    return Pose3D(fps=pose.fps, points=out, num_views=pose.num_views.copy())
