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


def smooth(pose: Pose3D) -> Pose3D:
    """
    Low-pass each joint trajectory with a Savitzky-Golay filter
    (config.SMOOTH_WINDOW_FRAMES, config.SMOOTH_POLYORDER). The window is
    small so fast motion such as a punch survives. Each continuous run is
    filtered on its own so NaN gaps don't spread; runs shorter than the
    window are left as they are.
    """
    from scipy.signal import savgol_filter

    p3ds = pose.points
    out = p3ds.copy()
    window, order = config.SMOOTH_WINDOW_FRAMES, config.SMOOTH_POLYORDER

    for j in range(p3ds.shape[1]):
        present = ~np.isnan(p3ds[:, j]).any(axis=1)
        for s, e in _runs(present):
            if e - s >= window:
                out[s:e, j] = savgol_filter(p3ds[s:e, j], window, order, axis=0)

    return Pose3D(fps=pose.fps, points=out, num_views=pose.num_views.copy())
