"""
Stage 2b, second half: things the calibration does not provide.

The calibration result has no real-world scale and is expressed in camera
0's frame. A rig file needs metres, a floor and an up direction.

Input : CameraRig (arbitrary units) + a rough Pose3D triangulated with it.
Output: the same CameraRig converted to metres, Y up, floor at Y = 0.

World axes after this step: Y up, Z pointing from the performer towards
camera 0 (along the floor), X to the right as seen from camera 0. The origin
is on the floor under the middle of where the performer's feet were.
"""
from __future__ import annotations

import numpy as np

from .. import config
from ..joints import JOINT_INDEX
from ..schemas import Camera, CameraRig, Pose3D


def _mid(points, *names):
    """Average of the named joints, (F, 3)."""
    return np.mean([points[:, JOINT_INDEX[n]] for n in names], axis=0)


def _body_axis(points):
    """Heel-to-ear vectors and which frames are standing upright."""
    heel = _mid(points, "LEFT_HEEL", "RIGHT_HEEL")
    ear = _mid(points, "LEFT_EAR", "RIGHT_EAR")
    axis = ear - heel
    length = np.linalg.norm(axis, axis=1)

    with np.errstate(invalid="ignore", divide="ignore"):
        unit = axis / length[:, None]

    # upright: knees, hips and shoulders all close to the heel-ear line
    with np.errstate(invalid="ignore"):
        upright = np.isfinite(length) & (length > 0)

    for names in (("LEFT_KNEE", "RIGHT_KNEE"), ("LEFT_HIP", "RIGHT_HIP"),
                  ("LEFT_SHOULDER", "RIGHT_SHOULDER")):
        v = _mid(points, *names) - heel
        off_line = np.linalg.norm(v - np.sum(v * unit, axis=1)[:, None] * unit, axis=1)

        with np.errstate(invalid="ignore"):
            upright &= off_line <= config.UPRIGHT_MAX_DEVIATION * length

    return unit, length, upright


def scale_factor_from_height(pose: Pose3D, performer_height_m: float) -> float:
    """
      1. Pick frames where the performer stands upright (heels, knees, hips,
         shoulders and ears roughly on one line).
      2. Measure heel-to-ear distance in rig units. Ears are the highest
         reliable landmark; the top of the skull and the heel's height above
         the floor are added as fixed offsets (config).
      3. Return (height minus offsets) / median(measured).
    """
    _, length, upright = _body_axis(pose.points)
    if upright.sum() < config.MIN_UPRIGHT_FRAMES:
        raise ValueError(
            f"only {int(upright.sum())} frames with the performer standing upright, need "
            f"{config.MIN_UPRIGHT_FRAMES} to measure their height (stand still for a moment, facing the cameras)")
    
    heel_to_ear_m = performer_height_m - config.HEAD_TOP_ABOVE_EARS_M - config.HEEL_ABOVE_FLOOR_M

    return heel_to_ear_m / float(np.median(length[upright]))


def estimate_floor(pose: Pose3D):
    """
      1. Rough up direction: the median heel-to-ear direction while upright.
      2. Collect heel and toe positions over all frames and keep the lowest
         ones along that direction (feet on the ground).
      3. Fit a plane to them (least squares). If the feet barely moved, the
         plane is unreliable and the rough up direction is used instead.
      4. Return the plane's normal (pointing towards the head) and a point on
         the floor (the heel landmarks sit config.HEEL_ABOVE_FLOOR_M above it,
         in the pose's units, so call this on a metric pose).
    """
    points = pose.points
    unit, _, upright = _body_axis(points)
    frames = upright if upright.sum() >= config.MIN_UPRIGHT_FRAMES else np.isfinite(unit).all(axis=1)
    up = np.median(unit[frames], axis=0)
    up /= np.linalg.norm(up)

    feet = points[:, [JOINT_INDEX[n] for n in
                      ("LEFT_HEEL", "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX")]].reshape(-1, 3)
    feet = feet[np.isfinite(feet).all(axis=1)]

    if len(feet) < 10:
        raise ValueError("feet seen in too few frames to find the floor")
    
    heights = feet @ up
    low = feet[heights <= np.quantile(heights, config.FLOOR_LOWEST_FRACTION)]
    centre = low.mean(axis=0)

    # plane through the low foot points: the normal is the direction they vary least in
    _, s, vt = np.linalg.svd(low - centre, full_matrices=False)
    normal = vt[2] if np.dot(vt[2], up) >= 0 else -vt[2]
    spread_ok = s[1] > 3 * s[2]            # the feet covered an area, not a line or a spot
    tilt_ok = np.degrees(np.arccos(np.clip(np.dot(normal, up), -1, 1))) < 30

    if not (spread_ok and tilt_ok):
        normal = up

    point = centre - normal * config.HEEL_ABOVE_FLOOR_M

    return normal, point


def make_metric(rig: CameraRig, pose: Pose3D, performer_height_m: float,
                rescale: bool = True) -> CameraRig:
    """
      1. Scale every camera's t by scale_factor_from_height (skipped with
         rescale=False, e.g. a ChArUco board calibration already in metres).
      2. Build the rotation that maps the floor normal to +Y (Z towards
         camera 0, X to its right) and the translation that puts the floor
         at Y = 0, under the middle of the performer's footprint.
      3. Apply that world transform to every camera's R and t.
      4. Set rig.is_metric = True.
    """
    scale = scale_factor_from_height(pose, performer_height_m) if rescale else 1.0
    scaled = Pose3D(fps=pose.fps, points=pose.points * scale, num_views=pose.num_views)
    normal, floor_point = estimate_floor(scaled)

    # camera 0's centre, in the scaled old world
    cam0 = rig.cameras[0]
    c0 = -cam0.R.T @ (cam0.t * scale)
    toward = c0 - floor_point
    toward -= np.dot(toward, normal) * normal

    if np.linalg.norm(toward) < 1e-9:
        toward = np.cross(normal, [1.0, 0.0, 0.0])

    z = toward / np.linalg.norm(toward)
    y = normal
    x = np.cross(y, z)
    A = np.array([x, y, z])                 # new world axes, as rows in old coordinates

    cameras = []

    for cam in rig.cameras:
        t = cam.t * scale
        # x_cam = R X_old + t and X_old = A^T X_new + floor_point
        R_new = cam.R @ A.T
        t_new = t + cam.R @ floor_point
        cameras.append(Camera(camera_id=cam.camera_id, K=cam.K, R=R_new, t=t_new))

    print(f"Scale: {scale:.4f} m per unit, floor found, Y up")
    
    return CameraRig(cameras=cameras, reprojection_error_px=dict(rig.reprojection_error_px), is_metric=True)
