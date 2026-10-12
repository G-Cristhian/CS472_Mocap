"""
Quality metric for a camera layout (paper sections 3.1 to 3.4).

Idea: for one target point, imagine a vertical wall through the point,
rotated through all 360 degrees. For each orientation, only cameras on the
front side can see the point. The point's error is the total angle over which
no two front-side cameras form a usable triangulation pair. 0 is perfect,
360 is never reconstructable.
"""

from __future__ import annotations

import numpy as np

from .. import config
from ..schemas import CameraRig


def camera_sees(camera, point) -> bool:
    """
    True if the point projects inside the image and is closer than
    config.CAMERA_EFFECTIVE_RANGE_M (section 3.2).
    """
    # camera... name, k (zoom)... r (where it's facing)... t (where it's standing)
    # X, Y, Z (straight ahead)
    in_cam = np.asarray(camera.R) @ np.asarray(point, dtype=float) + np.asarray(
        camera.t
    )

    if in_cam[2] <= 0:  # Check if the user is in front of the camera
        return False

    # Where the point lands
    u, v, w = np.asarray(camera.K) @ in_cam
    x, y = u / w, v / w

    # Calibration puts the image centre at K[0, 2], K[1, 2] so the image is twice that
    width, height = 2 * camera.K[0][2], 2 * camera.K[1][2]

    if not (0 <= x <= width and 0 <= y <= height):
        return False

    return bool(np.linalg.norm(in_cam) <= config.CAMERA_EFFECTIVE_RANGE_M)


def is_triangulable(camera_a, camera_b, point) -> bool:
    """
    TODO: angle between the two rays from the point to each camera centre
    lies in [config.MIN_CONVERGENCE_DEG, config.MAX_CONVERGENCE_DEG]
    (section 3.1).
    """
    raise NotImplementedError


def point_error(rig: CameraRig, point) -> float:
    """
    The algorithm of section 3.4 plus the penalty of equation 1.

    TODO:
      1. Cameras that see the point. None: return 360 + penalty. One: 360.
      2. Project each camera's view direction onto the floor plane. These
         directions and their opposites split the circle of wall orientations
         into sections where the front-side camera set is constant.
      3. For each section, test its middle orientation: is there any
         triangulable pair among the front-side cameras? If not, add the
         section's angular size to the error.
    """
    raise NotImplementedError


def layout_cost(rig: CameraRig, target_points) -> float:
    """Sum of point_error over all target points (paper equation 2)."""
    raise NotImplementedError


def target_points_from_pose(pose) -> list:
    """
    TODO: sample joint positions from a recorded Pose3D so the layout is
    scored on where the performer actually moved. Fall back to a uniform
    grid over the capture volume when no recording exists yet.
    """
    raise NotImplementedError
