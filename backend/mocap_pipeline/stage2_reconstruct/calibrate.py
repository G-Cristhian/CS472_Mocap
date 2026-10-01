"""
Stage 2b: checkerboard-free calibration from the performer's own joints.

Method: Liu et al. 2022, "Auto calibration of multi-camera system for human
pose estimation", IET Computer Vision, DOI 10.1049/cvi2.12130.
Section numbers in the comments refer to that paper.

Input : synced Keypoints2D for every camera (frame i = same instant).
Output: CameraRig. Units are arbitrary and the world frame is camera 0's
        frame; scale_floor.py fixes both afterwards.

Best results need the performer to move through the whole shared view with
arms and legs stretched (paper section 3).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import Camera, CameraRig, Keypoints2D

if TYPE_CHECKING:
    import numpy as np


def initial_intrinsics(width: int, height: int) -> "np.ndarray":
    """
    First guess at K for a phone camera.

    TODO: principal point at the image centre; focal length in pixels from
    config.DEFAULT_HFOV_DEG: f = (width / 2) / tan(hfov / 2). Skew = 0.
    """
    raise NotImplementedError


def select_correspondences(a: Keypoints2D, b: Keypoints2D
                           ) -> tuple["np.ndarray", "np.ndarray"]:
    """
    Matching 2D points seen by both cameras (section 3, data selection).

    TODO: over all frames and joints.CALIBRATION_JOINTS, keep a point only if
    confidence >= config.CALIB_MIN_CONFIDENCE in BOTH cameras.
    Return two (N, 2) arrays, row i in each being the same joint at the same
    instant. Raise if N is too small to calibrate (say under 200).
    """
    raise NotImplementedError


def estimate_relative_pose(pts_a, pts_b, K_a, K_b):
    """
    Rotation and translation of camera b relative to camera a (section 4.2.1).

    TODO:
      1. Fundamental matrix F with RANSAC (cv2.findFundamentalMat).
      2. Essential matrix E = K_b^T F K_a.
      3. Decompose E into four (R, t) candidates and keep the one that puts
         the triangulated joints in front of both cameras (cv2.recoverPose
         does steps 2 and 3).
      4. t comes out with length 1: scale is unknown here by design.
    """
    raise NotImplementedError


def refine_intrinsics(pts_a, pts_b, K_a, K_b, R, t):
    """
    Section 4.2.2. Hold R, t fixed; triangulate the points; adjust each K by
    least squares to minimise reprojection error (paper equation 5).
    TODO: scipy.optimize.least_squares over fx, fy, cx, cy of each camera.
    """
    raise NotImplementedError


def reprojection_error(pts_2d, pts_3d, K, R, t) -> float:
    """Mean pixel distance between detected and reprojected joints (eq. 8)."""
    raise NotImplementedError


def calibrate_pair(a: Keypoints2D, b: Keypoints2D,
                   K_a_fixed: "np.ndarray | None" = None) -> tuple[Camera, Camera]:
    """
    Binocular calibration loop (section 4.2).

    TODO:
      1. K from initial_intrinsics, unless K_a_fixed is given (used when
         adding a camera to an existing rig: the reference stays untouched).
      2. Loop: estimate_relative_pose -> refine_intrinsics ->
         reprojection_error. Stop when the error improves by less than
         config.CALIB_CONVERGENCE_PX or after config.CALIB_MAX_ITERATIONS.
      3. Camera a gets R = identity, t = 0.
    """
    raise NotImplementedError


def calibrate_rig(keypoints: list[Keypoints2D]) -> CameraRig:
    """
    Multi-camera calibration (section 4.3). Needs at least two cameras.

    TODO:
      1. Initialise: calibrate_pair(camera 0, camera 1). Then for each
         further camera i, calibrate_pair(camera 0, camera i) with camera 0's
         K fixed.
      2. Joint extrinsic optimisation: triangulate confident joints using all
         cameras, then refine each camera's translation against reprojection
         error, keeping |t| of camera 1 at 1 so the scale cannot drift
         (paper equation 9).
      3. Joint optimisation of intrinsics and extrinsics together; repeat 2-3
         until the mean reprojection error stops decreasing.
      4. Fill CameraRig.reprojection_error_px per camera.
    If camera i shares too little view with camera 0, pair it with whichever
    already-calibrated camera it overlaps most and chain the transforms.
    """
    raise NotImplementedError


def add_camera(rig: CameraRig, existing: list[Keypoints2D],
               new: Keypoints2D) -> CameraRig:
    """
    Add one phone to an already calibrated rig without redoing everything.
    TODO: step 1 of calibrate_rig for the new camera only, then one pass of
    steps 2-3 over the whole rig.
    """
    raise NotImplementedError
