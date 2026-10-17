"""
Quality metric for a camera layout (paper sections 3.1 to 3.4).

Idea: for one target point, imagine a vertical wall through the point,
rotated through all 360 degrees. For each orientation, only cameras on the
front side can see the point. The point's error is the total angle over which
no two front-side cameras form a usable triangulation pair. 0 is perfect,
360 is never reconstructable.

Method: Rahimian & Kearney 2015, "Optimal Camera Placement for Motion Capture
Systems in the Presence of Dynamic Occlusion", VRST, DOI
10.1145/2821592.2821596. World frame is the pipeline's: metres, Y up, floor
at Y = 0, so "the floor plane" is the x-z plane.
"""

from __future__ import annotations

import numpy as np

from .. import config
from ..schemas import CameraRig


def camera_centre(camera) -> np.ndarray:
    """Where the camera stands, in world coordinates (x_cam = R X + t, so X = -R^T t)."""
    R, t = np.asarray(camera.R, dtype=float), np.asarray(camera.t, dtype=float)
    return -R.T @ t


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


def convergence_angle_deg(camera_a, camera_b, point) -> float:
    """Angle at the point between the rays to the two camera centres, in degrees."""
    p = np.asarray(point, dtype=float)
    a, b = camera_centre(camera_a) - p, camera_centre(camera_b) - p
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))))


def is_triangulable(camera_a, camera_b, point) -> bool:
    """
    The angle between the two rays from the point to each camera centre lies
    in [config.MIN_CONVERGENCE_DEG, config.MAX_CONVERGENCE_DEG] (section 3.1).
    Rays nearly parallel give poor depth; rays nearly opposite see opposite
    sides of the body and rarely both see the same joint.
    """
    angle = convergence_angle_deg(camera_a, camera_b, point)
    return config.MIN_CONVERGENCE_DEG <= angle <= config.MAX_CONVERGENCE_DEG


def _floor_azimuth(direction) -> float:
    """Angle of a direction projected onto the floor (x-z plane), radians in [0, 2 pi)."""
    return float(np.arctan2(direction[0], direction[2]) % (2 * np.pi))


def point_error(rig: CameraRig, point) -> float:
    """
    The algorithm of section 3.4 plus the uncovered-point penalty (equation 1).

      1. Cameras that see the point. None: 360 + config.PLACEMENT_UNCOVERED_PENALTY_DEG.
         One: 360.
      2. Project each camera's direction from the point onto the floor plane.
         A wall through the point with outward normal at angle theta has a
         camera on its front side when the angle between the normal and the
         camera's floor direction is under 90 degrees. The front-side set
         changes only at theta = azimuth +- 90 degrees for each camera, so
         those angles split the circle into sections where the set is constant.
      3. For each section, test its middle orientation: is there any
         triangulable pair among the front-side cameras? If not, add the
         section's angular size to the error.
    """
    p = np.asarray(point, dtype=float)
    seeing = [c for c in rig.cameras if camera_sees(c, p)]
    if not seeing:
        return 360.0 + config.PLACEMENT_UNCOVERED_PENALTY_DEG
    if len(seeing) == 1:
        return 360.0

    azimuth = np.array([_floor_azimuth(camera_centre(c) - p) for c in seeing])
    n = len(seeing)
    pair_ok = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for j in range(i + 1, n):
            pair_ok[i, j] = pair_ok[j, i] = is_triangulable(seeing[i], seeing[j], p)

    bounds = np.sort(np.concatenate([(azimuth + np.pi / 2) % (2 * np.pi),
                                     (azimuth - np.pi / 2) % (2 * np.pi)]))
    edges = np.concatenate([bounds, [bounds[0] + 2 * np.pi]])

    error = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        if hi <= lo:
            continue
        middle = (lo + hi) / 2
        front = np.flatnonzero(np.cos(middle - azimuth) > 0)
        if not pair_ok[np.ix_(front, front)].any():
            error += np.degrees(hi - lo)
    return float(error)


def layout_cost(rig: CameraRig, target_points) -> float:
    """Sum of point_error over all target points (paper equation 2)."""
    return float(sum(point_error(rig, p) for p in np.asarray(target_points, dtype=float).reshape(-1, 3)))


def target_points_from_pose(pose=None, max_points: int = config.PLACEMENT_MAX_TARGET_POINTS,
                            seed: int = 0) -> np.ndarray:
    """
    (N, 3) points to score a layout on. From a recorded Pose3D: the finite
    joint positions, subsampled to at most max_points so the layout is scored
    on where the performer actually moved. Without a recording: a grid over
    the capture volume (config.PLACEMENT_GRID_*).
    """
    if pose is None:
        half, step = config.PLACEMENT_GRID_HALF_WIDTH_M, config.PLACEMENT_GRID_STEP_M
        axis = np.arange(-half, half + 1e-9, step)
        xs, ys, zs = np.meshgrid(axis, np.asarray(config.PLACEMENT_GRID_HEIGHTS_M, dtype=float), axis, indexing="ij")
        return np.stack([xs.ravel(), ys.ravel(), zs.ravel()], axis=1)

    points = np.asarray(pose.points, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) > max_points:
        rng = np.random.default_rng(seed)
        points = points[np.sort(rng.choice(len(points), size=max_points, replace=False))]
    return points
