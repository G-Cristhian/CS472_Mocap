"""
Stage 2b, second half: things the calibration paper does not provide.

The paper's result has no real-world scale and is expressed in camera 0's
frame. A rig file needs metres, a floor and an up direction.

Input : CameraRig (arbitrary units) + a rough Pose3D triangulated with it.
Output: the same CameraRig converted to metres, Y up, floor at Y = 0.
"""
from __future__ import annotations

from ..schemas import CameraRig, Pose3D


def scale_factor_from_height(pose: Pose3D, performer_height_m: float) -> float:
    """
    TODO:
      1. Pick frames where the performer stands upright (ankles, hips,
         shoulders, head roughly on one line).
      2. Measure heel-to-head-top distance in rig units. Ears are the highest
         reliable landmark; add a fixed offset for the top of the skull.
      3. Return performer_height_m / median(measured).
    """
    raise NotImplementedError


def estimate_floor(pose: Pose3D):
    """
    TODO:
      1. Collect heel and toe positions over all frames.
      2. Keep the lowest ones (feet in contact with the ground) and fit a
         plane (RANSAC or least squares).
      3. Return the plane's normal (pointing towards the head) and a point
         on it.
    """
    raise NotImplementedError


def make_metric(rig: CameraRig, pose: Pose3D, performer_height_m: float) -> CameraRig:
    """
    TODO:
      1. Scale every camera's t by scale_factor_from_height.
      2. Build the rotation that maps the floor normal to +Y and the
         translation that puts the floor at Y = 0.
      3. Apply that world transform to every camera's R and t.
      4. Set rig.is_metric = True.
    """
    raise NotImplementedError
