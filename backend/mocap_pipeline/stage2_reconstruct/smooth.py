"""
Stage 2c, clean-up: fill short gaps and remove jitter.

Input : raw Pose3D.  Output: cleaned Pose3D, same shape.
"""
from __future__ import annotations

from ..schemas import Pose3D


def fill_gaps(pose: Pose3D) -> Pose3D:
    """
    TODO: per joint and axis, interpolate runs of NaN no longer than
    config.MAX_GAP_FILL_FRAMES. Leave longer gaps as NaN and report them.
    """
    raise NotImplementedError


def smooth(pose: Pose3D) -> Pose3D:
    """
    TODO: low-pass filter each joint trajectory. Start with a Savitzky-Golay
    or Butterworth filter (scipy.signal); keep the cutoff in config.py.
    Do not over-smooth: fast motion such as a punch must survive.
    """
    raise NotImplementedError
