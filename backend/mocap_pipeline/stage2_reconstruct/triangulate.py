"""
Stage 2c: combine every camera's 2D joints into one 3D point per joint.

Input : synced Keypoints2D for every camera + CameraRig.
Output: Pose3D (raw, before smoothing).
"""
from __future__ import annotations

import numpy as np

from .. import config
from ..schemas import CameraRig, Keypoints2D, Pose3D
from .calibrate import rig_to_group


def triangulate_point(points_2d, confidences, projection_matrices):
    """
    One joint in one frame, weighted by confidence. NOT USED: our
    triangulate_sequence triangulates every joint of every frame at once with
    aniposelib (linear DLT, unweighted). Left as the outline's placeholder.
    """
    raise NotImplementedError


def triangulate_sequence(keypoints: list[Keypoints2D], rig: CameraRig) -> Pose3D:
    """
      1. For every frame and joint, use only cameras with confidence >=
         config.TRIANGULATION_MIN_CONFIDENCE. Fewer than 2 cameras: NaN and
         num_views = 0.
      2. Outlier check: reproject into each contributing camera; if one camera
         is further off than config.MAX_REPROJECTION_ERROR_PX, drop it and
         triangulate again (as long as 2 cameras remain).
      3. Joints still off after that are dropped.
    """
    cgroup = rig_to_group(rig)
    points = np.stack([kp.points for kp in keypoints])          # (n_cams, F, J, 2)
    confidence = np.stack([kp.confidence for kp in keypoints])  # (n_cams, F, J)
    n_cams, n_frames, n_joints, _ = points.shape

    points = points.copy()
    points[confidence < config.TRIANGULATION_MIN_CONFIDENCE] = np.nan
    p2ds = points.reshape(n_cams, -1, 2)
    p3ds = cgroup.triangulate(p2ds)
    max_error = config.MAX_REPROJECTION_ERROR_PX

    # with 3+ cameras, a joint mis-detected in one camera is fixed by leaving that view out
    for _ in range(n_cams - 2):
        per_cam = np.linalg.norm(cgroup.reprojection_error(p3ds, p2ds), axis=2)  # (n_cams, n_points)
        n_views = np.sum(~np.isnan(per_cam), axis=0)
        bad = (np.nanmax(np.nan_to_num(per_cam, nan=-1.0), axis=0) > max_error) & (n_views > 2)

        if not bad.any():
            break

        worst = np.nanargmax(np.nan_to_num(per_cam[:, bad], nan=-1.0), axis=0)
        p2ds = p2ds.copy()
        p2ds[worst, np.flatnonzero(bad)] = np.nan
        p3ds[bad] = cgroup.triangulate(p2ds[:, bad])

    # drop joints whose reprojection is still far off
    errors = cgroup.reprojection_error(p3ds, p2ds, mean=True)
    failed = ~(errors < max_error)
    p3ds[failed] = np.nan

    num_views = np.sum(~np.isnan(p2ds[:, :, 0]), axis=0)
    num_views[failed] = 0
    
    return Pose3D(fps=keypoints[0].fps,
                  points=p3ds.reshape(n_frames, n_joints, 3),
                  num_views=num_views.reshape(n_frames, n_joints))
