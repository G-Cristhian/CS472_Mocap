import cv2
import numpy as np

from aniposelib.cameras import Camera, CameraGroup
from extract_2d import LANDMARK_NAMES


class PersonCalibrationError(Exception):
    pass

# function to create camera matrix using the image's size + camera's horizontal fov!
#   typically: phones = 60-75 degrees on main lens, webcams = 60-80
def guess_intrinsics(size, fov_deg=65.0):
    width, height = size
    f = (width / 2.0) / np.tan(np.radians(fov_deg) / 2.0)

    return np.array([[f, 0, width / 2.0],
                     [0, f, height / 2.0],
                     [0, 0, 1.0]])

# function to calibrate 2-4 cameras using a person's determined landmarks.
#   grabs pixel coordinates from points field!
#   grabs measurments of each camera from sizes field
#   grabs body length measurements from scale _segment
#   grabs a camera matrix per camera if known (iPhone case), or guesses from fov_deg, from intrinsics
def calibrate_from_person(points, sizes, scale_segment, fov_deg=65.0, intrinsics=None,
                          refine_intrinsics=False, min_correspondences=200, min_pnp_points=50):
    n_cams = points.shape[0]
    if n_cams < 2:
        raise ValueError("person calibration needs at least 2 cameras")

    # guessing from fov_deg if camera matrix not known
    if intrinsics is None:
        intrinsics = [guess_intrinsics(size, fov_deg) for size in sizes]
    
    cameras = [Camera(name=f"cam{c}", size=sizes[c], matrix=intrinsics[c]) for c in range(n_cams)]
    flat = points.reshape(n_cams, -1, 2)

    # start from the pair of cameras that saw the most distinct landmarks together
    pairs = [(a, b) for a in range(n_cams) for b in range(a + 1, n_cams)]
    counts = {(a, b): _n_distinct(flat[a], flat[b], sizes[a], sizes[b]) for a, b in pairs}
    a, b = max(pairs, key=lambda pair: counts[pair])

    # error messages
    if counts[(a, b)] < min_correspondences:
        raise PersonCalibrationError(
            f"only {counts[(a, b)]} distinct landmarks seen by two cameras together, "
            f"need {min_correspondences} (the person should move around more)")

    R, t, inlier_ratio = _relative_pose(flat[a], flat[b], intrinsics[a], intrinsics[b])

    # for now, camera a is set as origin while camera b is relative to it!
    cameras[b].set_rotation(cv2.Rodrigues(R)[0].ravel())
    cameras[b].set_translation(t.ravel())
    placed = [a, b]

    CameraGroup([cameras[a], cameras[b]]).bundle_adjust_iter(
        flat[placed], only_extrinsics=not refine_intrinsics, verbose=False)

    # adds cameras one at a time by amount of 3D points captured!
    while len(placed) < n_cams:
        p3ds = CameraGroup([cameras[c] for c in placed]).triangulate(flat[placed])
        known = np.isfinite(p3ds).all(axis=1)
        unplaced = [c for c in range(n_cams) if c not in placed]
        seen = {c: known & ~np.isnan(flat[c]).any(axis=1) for c in unplaced}
        c = max(unplaced, key=lambda c: seen[c].sum())

        # error messages!
        if seen[c].sum() < min_pnp_points:
            raise PersonCalibrationError(
                f"camera {c} saw too little of the person while the other cameras did "
                f"(the person should move around where all cameras can see them)")

        ok, rvec, tvec, inliers = cv2.solvePnPRansac(
            p3ds[seen[c]].astype(np.float64), flat[c][seen[c]].astype(np.float64),
            intrinsics[c], None, reprojectionError=8.0, iterationsCount=1000)

        # error message
        if not ok or inliers is None or len(inliers) < min_pnp_points:
            raise PersonCalibrationError(f"could not place camera {c} from the landmarks")
        
        cameras[c].set_rotation(rvec.ravel())
        cameras[c].set_translation(tvec.ravel())

        placed.append(c)

    # refine all cameras together on all the landmark matches
    cgroup = CameraGroup(cameras)
    
    if n_cams > 2:
        cgroup.bundle_adjust_iter(flat, only_extrinsics=not refine_intrinsics, verbose=False)

    # turns the first camera in list (camera 0) as origin
    _move_origin_to(cgroup, 0)

    # sets units to pose using known body length
    scale = _scale_from_segment(cgroup, points, scale_segment)

    for cam in cgroup.cameras:
        cam.set_translation(cam.get_translation() * scale)

    p3ds = cgroup.triangulate(flat)
    error = _mean_reprojection_error(cgroup, p3ds, flat)

    info = {
        "method": "person",
        "start_pair": (a, b),
        "correspondences": int((np.sum(~np.isnan(flat[:, :, 0]), axis=0) >= 2).sum()),
        "inlier_ratio": inlier_ratio,
        "reprojection_error_px": error,
        "scale": float(scale),
    }

    return cgroup, info

# function to count distinct positions seen by both cameras
#   on a grid of 1% of image width
#   this addresses a person standing still giving same points over and over alongside detection jitter
def _n_distinct(pa, pb, size_a, size_b):
    both = ~np.isnan(pa).any(axis=1) & ~np.isnan(pb).any(axis=1)
    grid = 0.01 * np.array([size_a[0], size_a[0], size_b[0], size_b[0]])

    return len(np.unique(np.round(np.hstack([pa[both], pb[both]]) / grid), axis=0))


# function to determine relative pose of camera b to camera a from the essential matrix
def _relative_pose(pa, pb, Ka, Kb):
    both = ~np.isnan(pa).any(axis=1) & ~np.isnan(pb).any(axis=1)

    # move to normalized camera coords so the two cameras can have different lenses
    na = cv2.undistortPoints(pa[both].reshape(-1, 1, 2), Ka, None)
    nb = cv2.undistortPoints(pb[both].reshape(-1, 1, 2), Kb, None)

    # RANSAC throws out bad landmark matches
    thresh = 3.0 / Ka[0, 0]
    E, mask = cv2.findEssentialMat(na, nb, focal=1.0, pp=(0.0, 0.0),
                                   method=cv2.RANSAC, prob=0.999, threshold=thresh)
    
    if E is None or E.shape != (3, 3):
        raise PersonCalibrationError("could not estimate camera pose from the landmarks")
    _, R, t, mask = cv2.recoverPose(E, na, nb, mask=mask)

    return R, t, float((mask > 0).mean())


# function that re-expresses every camera so camera origin stis at (0,0,0) looking down (+z)
def _move_origin_to(cgroup, origin):
    R0 = cv2.Rodrigues(cgroup.cameras[origin].get_rotation())[0]
    t0 = cgroup.cameras[origin].get_translation()

    for cam in cgroup.cameras:
        R = cv2.Rodrigues(cam.get_rotation())[0] @ R0.T
        cam.set_translation(cam.get_translation() - R @ t0)
        cam.set_rotation(cv2.Rodrigues(R)[0].ravel())

# function to scale using scale_segment
def _scale_from_segment(cgroup, points, scale_segment):
    name_a, name_b, length_m = scale_segment
    a, b = LANDMARK_NAMES.index(name_a), LANDMARK_NAMES.index(name_b)

    pair = points[:, :, [a, b], :]  # (n_cams, n_frames, 2, 2)
    p3 = cgroup.triangulate(pair.reshape(points.shape[0], -1, 2)).reshape(-1, 2, 3)
    lengths = np.linalg.norm(p3[:, 0] - p3[:, 1], axis=1)
    lengths = lengths[np.isfinite(lengths)]
    if len(lengths) < 10:
        raise PersonCalibrationError(f"{name_a}/{name_b} seen together in too few frames to set scale")

    # median ignores frames where one of the points was badly detected
    return length_m / np.median(lengths)


# function to calculate the mean reprojection error from collective camera group
def _mean_reprojection_error(cgroup, p3ds, p2ds):
    errors = cgroup.reprojection_error(p3ds, p2ds)  # (n_cams, n_points, 2)
    norms = np.linalg.norm(errors, axis=2)
    return float(np.nanmean(norms))
