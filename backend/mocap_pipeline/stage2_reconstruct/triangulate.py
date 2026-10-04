"""
Stage 2c: combine every camera's 2D joints into one 3D point per joint.

Input : synced Keypoints2D for every camera + CameraRig.
Output: Pose3D (raw, before smoothing).
"""
from __future__ import annotations

from ..schemas import CameraRig, Keypoints2D, Pose3D


def triangulate_point(points_2d, confidences, projection_matrices):
    """
    One joint in one frame, from N >= 2 cameras.

    TODO: weighted linear triangulation (DLT). Each camera contributes two
    rows to a matrix A built from its projection matrix P = K [R | t] and its
    pixel coordinates, each row multiplied by that camera's confidence.
    The 3D point is the last right singular vector of A (np.linalg.svd),
    divided by its fourth component.
    """
    raise NotImplementedError


def triangulate_sequence(keypoints: list[Keypoints2D], rig: CameraRig) -> Pose3D:
    """
    TODO:
      1. Precompute P for each camera.
      2. For every frame and joint, use only cameras with confidence >=
         config.TRIANGULATION_MIN_CONFIDENCE. Fewer than
         config.MIN_CAMERAS_PER_JOINT: leave NaN and num_views = 0.
      3. Outlier check: reproject the result into each contributing camera;
         if one camera is far off, drop it and triangulate again.
      4. Return Pose3D at config.TARGET_FPS.
    """
    raise NotImplementedError
