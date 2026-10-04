import json
import numpy as np

from extract_2d import LANDMARK_NAMES

# function that turns 2D landmarks into 3D
#   RETURNS (n_frames, 33, 3) in calibration's units (meters), NaN where point couldn't be placed
def triangulate_3d(cgroup, points, max_error_px=15.0):
    n_cams, n_frames, n_lm, _ = points.shape
    p2ds = points.reshape(n_cams, -1, 2)
    p3ds = cgroup.triangulate(p2ds)

    # in case of 3 <= cameras, landmark mis-detected in one camera is fixed by leaving it out
    #   drop worst view of each bad point then triangulate again
    for _ in range(n_cams - 2): # only does so if at least 2 cameras
        per_cam = np.linalg.norm(cgroup.reprojection_error(p3ds, p2ds), axis=2)  # (n_cams, n_points)
        n_views = np.sum(~np.isnan(per_cam), axis=0)
        bad = (np.nanmax(np.nan_to_num(per_cam, nan=-1.0), axis=0) > max_error_px) & (n_views > 2)

        if not bad.any():
            break

        worst = np.nanargmax(np.nan_to_num(per_cam[:, bad], nan=-1.0), axis=0)
        p2ds = p2ds.copy()
        p2ds[worst, np.flatnonzero(bad)] = np.nan
        p3ds[bad] = cgroup.triangulate(p2ds[:, bad])

    # drop points whose reprojection is still far off
    errors = cgroup.reprojection_error(p3ds, p2ds, mean=True)
    p3ds[~(errors < max_error_px)] = np.nan

    return p3ds.reshape(n_frames, n_lm, 3)

# function to write 3D landmarks as JSON for frontend
def save_json(p3ds, fps, path, times=None):
    frames = []
    for f, frame in enumerate(p3ds):
        landmarks = {}
        for name, p in zip(LANDMARK_NAMES, frame):
            landmarks[name] = None if np.isnan(p).any() else {
                "x": round(float(p[0]), 4), "y": round(float(p[1]), 4), "z": round(float(p[2]), 4)}
        t = times[f] if times is not None else f / fps
        frames.append({"t": round(float(t), 4), "landmarks": landmarks})

    with open(path, "w") as fp:
        json.dump(frames, fp)
