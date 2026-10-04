"""
Stage 2b: checkerboard-free calibration from the performer's own joints.

Method: OURS, not Liu et al. 2022. Both calibrate from the performer's joints,
but ours keeps each camera's lens fixed (iPhones read the real focal length
from the video metadata, other cameras use the field of view) and places the
cameras like this:
  1. Find the two cameras that saw the most of the performer together and
     get their relative pose from the joints (essential matrix, RANSAC).
  2. Add every other camera from the performer's 3D points (solvePnP).
  3. Refine all cameras together (aniposelib bundle adjustment).
  4. Re-express everything with camera 0 at the origin.
Liu et al.'s intrinsic refinement (refine_intrinsics) is left unimplemented.
If this calibration fails, run_pipeline.py falls back to the ChArUco board
(board_calibration.py).

Input : synced Keypoints2D for every camera (frame i = same instant).
Output: CameraRig. Units are arbitrary and the world frame is camera 0's
        frame; scale_floor.py fixes both afterwards.

Best results need the performer to move through the whole shared view with
arms and legs stretched (paper section 3).
"""
from __future__ import annotations

import cv2
import numpy as np

from .. import config
from ..joints import CALIBRATION_JOINTS, JOINT_INDEX
from ..schemas import Camera, CameraRig, Keypoints2D


class CalibrationError(Exception):
    """Calibration from the performer failed; record more movement or use the board."""


# ---- conversion between schemas.Camera and aniposelib's cameras ----------------

def rig_to_group(rig: CameraRig):
    """aniposelib CameraGroup from a CameraRig (pinhole, no distortion)."""
    from aniposelib.cameras import Camera as AniCamera, CameraGroup

    return CameraGroup([
        AniCamera(name=c.camera_id, matrix=c.K, rvec=cv2.Rodrigues(c.R)[0].ravel(), tvec=c.t)
        for c in rig.cameras])


def group_to_rig(cgroup, camera_ids: list[str], errors: dict | None = None,
                 is_metric: bool = False) -> CameraRig:
    """CameraRig from an aniposelib CameraGroup."""
    cameras = [
        Camera(camera_id=cid, K=np.array(cam.get_camera_matrix(), dtype=float),
               R=cv2.Rodrigues(np.asarray(cam.get_rotation(), dtype=float))[0],
               t=np.array(cam.get_translation(), dtype=float).ravel())
        for cid, cam in zip(camera_ids, cgroup.cameras)]
    
    return CameraRig(cameras=cameras, reprojection_error_px=errors or {}, is_metric=is_metric)


def _stack(keypoints: list[Keypoints2D]):
    """(n_cams, n_frames, J, 2) points and (n_cams, n_frames, J) confidence."""

    return (np.stack([kp.points for kp in keypoints]),
            np.stack([kp.confidence for kp in keypoints]))


def _calibration_points(points, confidence):
    """Only stable body joints seen confidently; everything else becomes NaN."""
    keep = np.zeros(points.shape[2], dtype=bool)
    keep[[JOINT_INDEX[name] for name in CALIBRATION_JOINTS]] = True
    calib = points.copy()
    calib[:, :, ~keep] = np.nan
    calib[confidence < config.CALIB_MIN_CONFIDENCE] = np.nan

    return calib


def _n_distinct(pa, pb, size_a, size_b):
    """
    Distinct positions seen by both cameras, on a grid of 1% of the image width.
    A performer standing still gives the same few points over and over (plus
    detection jitter), so raw counts would overstate how much they moved.
    """
    both = ~np.isnan(pa).any(axis=1) & ~np.isnan(pb).any(axis=1)
    grid = 0.01 * np.array([size_a[0], size_a[0], size_b[0], size_b[0]])

    return len(np.unique(np.round(np.hstack([pa[both], pb[both]]) / grid), axis=0))


def _move_origin_to(cgroup, origin: int):
    """Re-express every camera so camera `origin` sits at (0, 0, 0) looking down +z."""
    R0 = cv2.Rodrigues(cgroup.cameras[origin].get_rotation())[0]
    t0 = cgroup.cameras[origin].get_translation()

    for cam in cgroup.cameras:
        R = cv2.Rodrigues(cam.get_rotation())[0] @ R0.T
        cam.set_translation(cam.get_translation() - R @ t0)
        cam.set_rotation(cv2.Rodrigues(R)[0].ravel())


def _per_camera_errors(cgroup, flat, camera_ids) -> dict[str, float]:
    """Mean reprojection error in pixels per camera."""
    p3ds = cgroup.triangulate(flat)
    norms = np.linalg.norm(cgroup.reprojection_error(p3ds, flat), axis=2)  # (n_cams, n_points)

    return {cid: float(np.nanmean(norms[c])) for c, cid in enumerate(camera_ids)}


# ---- the outline's functions -------------------------------------------------

def initial_intrinsics(width: int, height: int, hfov_deg: float = config.DEFAULT_HFOV_DEG) -> "np.ndarray":
    """
    First guess at K for a camera: principal point at the image centre, focal
    length in pixels from the horizontal field of view, skew 0.
    Phones are usually 60-75 degrees on the main lens, webcams 60-80.
    """
    f = (width / 2.0) / np.tan(np.radians(hfov_deg) / 2.0)

    return np.array([[f, 0, width / 2.0],
                     [0, f, height / 2.0],
                     [0, 0, 1.0]])


def select_correspondences(a: Keypoints2D, b: Keypoints2D
                           ) -> tuple["np.ndarray", "np.ndarray"]:
    """
    Matching 2D points seen by both cameras (section 3, data selection):
    joints.CALIBRATION_JOINTS with confidence >= config.CALIB_MIN_CONFIDENCE
    in BOTH cameras. Returns two (N, 2) arrays, row i in each being the same
    joint at the same instant. Raises if the performer did not move enough.
    """
    points, confidence = _stack([a, b])
    calib = _calibration_points(points, confidence).reshape(2, -1, 2)
    both = ~np.isnan(calib).any(axis=2).any(axis=0)
    n = _n_distinct(calib[0], calib[1], (a.width, a.height), (b.width, b.height))

    if n < config.CALIB_MIN_CORRESPONDENCES:
        raise CalibrationError(
            f"only {n} distinct joints seen by {a.camera_id} and {b.camera_id} together, "
            f"need {config.CALIB_MIN_CORRESPONDENCES} (the performer should move around more)")
    
    return calib[0][both], calib[1][both]


def estimate_relative_pose(pts_a, pts_b, K_a, K_b):
    """
    Rotation and translation of camera b relative to camera a (section 4.2.1).
    Points go to normalized camera coordinates (so the two cameras can have
    different lenses), then essential matrix with RANSAC and cv2.recoverPose,
    which keeps the (R, t) that puts the joints in front of both cameras.
    t comes out with length 1: scale is unknown here by design.
    """
    na = cv2.undistortPoints(pts_a.reshape(-1, 1, 2).astype(np.float64), K_a, None)
    nb = cv2.undistortPoints(pts_b.reshape(-1, 1, 2).astype(np.float64), K_b, None)
    thresh = config.RANSAC_REPROJ_THRESHOLD_PX / K_a[0, 0]

    E, mask = cv2.findEssentialMat(na, nb, focal=1.0, pp=(0.0, 0.0),
                                   method=cv2.RANSAC, prob=0.999, threshold=thresh)
    
    if E is None or E.shape != (3, 3):
        raise CalibrationError("could not estimate camera pose from the joints")
    
    _, R, t, mask = cv2.recoverPose(E, na, nb, mask=mask)

    return R, t.ravel()


def refine_intrinsics(pts_a, pts_b, K_a, K_b, R, t):
    """
    Section 4.2.2 of Liu et al. NOT USED: our calibration keeps each lens fixed
    (iPhone metadata or field of view). Left as the outline's placeholder.
    """
    raise NotImplementedError


def reprojection_error(pts_2d, pts_3d, K, R, t) -> float:
    """Mean pixel distance between detected and reprojected joints (eq. 8)."""
    proj, _ = cv2.projectPoints(np.asarray(pts_3d, dtype=np.float64).reshape(-1, 1, 3),
                                cv2.Rodrigues(np.asarray(R, dtype=np.float64))[0],
                                np.asarray(t, dtype=np.float64), np.asarray(K, dtype=np.float64), None)
    err = np.linalg.norm(proj.reshape(-1, 2) - np.asarray(pts_2d).reshape(-1, 2), axis=1)

    return float(np.nanmean(err))


def calibrate_pair(a: Keypoints2D, b: Keypoints2D,
                   K_a_fixed: "np.ndarray | None" = None,
                   K_b_fixed: "np.ndarray | None" = None) -> tuple[Camera, Camera]:
    """
    Two-camera calibration: relative pose from the joints, then both cameras
    refined together. Camera a gets R = identity, t = 0. Lenses stay as given
    (K_*_fixed, e.g. from iPhone metadata) or initial_intrinsics.
    """
    from aniposelib.cameras import Camera as AniCamera, CameraGroup

    K_a = K_a_fixed if K_a_fixed is not None else initial_intrinsics(a.width, a.height)
    K_b = K_b_fixed if K_b_fixed is not None else initial_intrinsics(b.width, b.height)
    pts_a, pts_b = select_correspondences(a, b)
    R, t = estimate_relative_pose(pts_a, pts_b, K_a, K_b)

    cgroup = CameraGroup([AniCamera(name=a.camera_id, matrix=K_a),
                          AniCamera(name=b.camera_id, matrix=K_b,
                                    rvec=cv2.Rodrigues(R)[0].ravel(), tvec=t)])
    
    points, confidence = _stack([a, b])
    flat = _calibration_points(points, confidence).reshape(2, -1, 2)
    cgroup.bundle_adjust_iter(flat, only_extrinsics=True, verbose=False)
    _move_origin_to(cgroup, 0)
    rig = group_to_rig(cgroup, [a.camera_id, b.camera_id])

    return rig.cameras[0], rig.cameras[1]


def _place_camera(placed_group, flat_placed, flat_new, K_new, name):
    """solvePnP for a new camera from the 3D joints the placed cameras see."""
    p3ds = placed_group.triangulate(flat_placed)
    seen = np.isfinite(p3ds).all(axis=1) & ~np.isnan(flat_new).any(axis=1)

    if seen.sum() < config.CALIB_MIN_PNP_POINTS:
        raise CalibrationError(
            f"camera {name} saw too little of the performer while the other cameras did "
            f"(the performer should move around where all cameras can see them)")
    
    ok, rvec, tvec, inliers = cv2.solvePnPRansac(
        p3ds[seen].astype(np.float64), flat_new[seen].astype(np.float64), K_new, None,
        reprojectionError=8.0, iterationsCount=1000)
    
    if not ok or inliers is None or len(inliers) < config.CALIB_MIN_PNP_POINTS:
        raise CalibrationError(f"could not place camera {name} from the joints")
    
    return rvec.ravel(), tvec.ravel()


def calibrate_rig(keypoints: list[Keypoints2D],
                  intrinsics: "list[np.ndarray] | None" = None) -> CameraRig:
    """
    Multi-camera calibration (2 to 4 cameras), our method:
      1. Start from the pair of cameras that saw the most distinct joints
         together (calibrate_pair's steps).
      2. Add the other cameras one at a time, the one that sees the most of
         the triangulated joints first (solvePnP).
      3. Refine all cameras together (bundle adjustment).
      4. Camera 0 becomes the origin; fill reprojection_error_px per camera.
    intrinsics: one K per camera if known (iPhone metadata), else initial_intrinsics.
    """
    from aniposelib.cameras import Camera as AniCamera, CameraGroup

    n_cams = len(keypoints)

    if n_cams < 2:
        raise ValueError("calibration needs at least two cameras")
    if intrinsics is None:
        intrinsics = [initial_intrinsics(kp.width, kp.height) for kp in keypoints]

    ids = [kp.camera_id for kp in keypoints]
    sizes = [(kp.width, kp.height) for kp in keypoints]

    points, confidence = _stack(keypoints)
    flat = _calibration_points(points, confidence).reshape(n_cams, -1, 2)
    cameras = [AniCamera(name=ids[c], size=sizes[c], matrix=intrinsics[c]) for c in range(n_cams)]

    # 1. best-matched pair
    pairs = [(a, b) for a in range(n_cams) for b in range(a + 1, n_cams)]

    counts = {(a, b): _n_distinct(flat[a], flat[b], sizes[a], sizes[b]) for a, b in pairs}
    a, b = max(pairs, key=lambda pair: counts[pair])

    pts_a, pts_b = select_correspondences(keypoints[a], keypoints[b])
    R, t = estimate_relative_pose(pts_a, pts_b, intrinsics[a], intrinsics[b])

    cameras[b].set_rotation(cv2.Rodrigues(R)[0].ravel())
    cameras[b].set_translation(t)
    placed = [a, b]

    CameraGroup([cameras[a], cameras[b]]).bundle_adjust_iter(
        flat[placed], only_extrinsics=True, verbose=False)
    
    print(f"Calibration started from {ids[a]} and {ids[b]}")

    # 2. add the rest
    while len(placed) < n_cams:
        group = CameraGroup([cameras[c] for c in placed])
        p3ds = group.triangulate(flat[placed])
        known = np.isfinite(p3ds).all(axis=1)
        unplaced = [c for c in range(n_cams) if c not in placed]
        c = max(unplaced, key=lambda c: (known & ~np.isnan(flat[c]).any(axis=1)).sum())
        rvec, tvec = _place_camera(group, flat[placed], flat[c], intrinsics[c], ids[c])
        cameras[c].set_rotation(rvec)
        cameras[c].set_translation(tvec)
        placed.append(c)

    # 3. refine together
    cgroup = CameraGroup(cameras)
    
    if n_cams > 2:
        cgroup.bundle_adjust_iter(flat, only_extrinsics=True, verbose=False)

    # 4. camera 0 is the world frame
    _move_origin_to(cgroup, 0)

    return group_to_rig(cgroup, ids, _per_camera_errors(cgroup, flat, ids))


def add_camera(rig: CameraRig, existing: list[Keypoints2D],
               new: Keypoints2D, K_new: "np.ndarray | None" = None) -> CameraRig:
    """
    Add one phone to an already calibrated rig without redoing everything:
    place it from the joints the existing cameras see (solvePnP), then one
    refinement pass over the whole rig.
    """
    from aniposelib.cameras import Camera as AniCamera, CameraGroup

    K_new = K_new if K_new is not None else initial_intrinsics(new.width, new.height)
    points, confidence = _stack(existing + [new])
    flat = _calibration_points(points, confidence).reshape(len(existing) + 1, -1, 2)

    group = rig_to_group(rig)
    rvec, tvec = _place_camera(group, flat[:-1], flat[-1], K_new, new.camera_id)
    cgroup = CameraGroup(group.cameras + [AniCamera(name=new.camera_id, matrix=K_new, rvec=rvec, tvec=tvec)])
    cgroup.bundle_adjust_iter(flat, only_extrinsics=True, verbose=False)
    _move_origin_to(cgroup, 0)

    ids = [c.camera_id for c in rig.cameras] + [new.camera_id]
    return group_to_rig(cgroup, ids, _per_camera_errors(cgroup, flat, ids), is_metric=False)
