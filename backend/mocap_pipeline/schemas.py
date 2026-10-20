"""
The contracts between stages. If a stage's output matches these shapes, the
next stage works regardless of how the previous one was implemented.

Conventions used everywhere:
  * Arrays are numpy arrays. J = joints.NUM_JOINTS (38: MediaPipe's 33, then joints.EXTRA_JOINTS). F = frame count.
  * Missing values are NaN, never 0.
  * 2D points are in pixels, origin top-left (convert MediaPipe's 0..1 values).
  * 3D points are in metres after scale_floor has run, Y up, floor at Y = 0.
  * Camera 0 (the first video given) is the reference camera.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass
class Keypoints2D:
    """Stage 1 output. One per camera."""
    camera_id: str            # stable name, e.g. the video file stem
    video_path: str
    width: int                # pixels
    height: int               # pixels
    fps: float                # nominal frame rate reported by the video
    timestamps: "np.ndarray"  # (F,)   seconds from the start of THIS video
    points: "np.ndarray"      # (F, J, 2) pixel x, y
    confidence: "np.ndarray"  # (F, J) 0..1, MediaPipe visibility score


@dataclass
class SyncResult:
    """Stage 2a output. Maps every camera onto one shared clock."""
    # camera_id -> seconds into that video at which the clap happens.
    clap_time_s: dict[str, float]
    # Shared timeline, t = 0 at the clap, sampled at config.TARGET_FPS.
    common_timestamps: "np.ndarray"   # (F_common,)


@dataclass
class Camera:
    """One calibrated camera (pinhole model, no lens distortion)."""
    camera_id: str
    K: "np.ndarray"   # (3, 3) intrinsics: focal lengths and principal point
    R: "np.ndarray"   # (3, 3) world -> camera rotation
    t: "np.ndarray"   # (3,)   world -> camera translation


@dataclass
class CameraRig:
    """Stage 2b output. Also the input to the placement tool."""
    cameras: list[Camera]
    # Mean reprojection error in pixels per camera; the calibration quality
    # number to show the user.
    reprojection_error_px: dict[str, float] = field(default_factory=dict)
    # False until scale_floor has converted units to metres and set Y up.
    is_metric: bool = False


@dataclass
class Pose3D:
    """Stage 2c output, stage 3 input."""
    fps: float
    points: "np.ndarray"        # (F, J, 3)
    # (F, J) number of cameras that contributed to each joint; 0 = gap.
    num_views: "np.ndarray"
