import numpy as np
from scipy.signal import savgol_filter

import config

# clean-up after triangulation: fill short gaps and remove jitter
# matches the smooth step of backend/mocap_pipeline (stage2_reconstruct/smooth.py)


# function to fill runs of missing frames no longer than config.MAX_GAP_FILL_FRAMES
#   by straight-line interpolation per landmark and axis, longer gaps stay NaN
#   p3ds: (n_frames, 33, 3), NaN where missing
def fill_gaps(p3ds, max_gap=config.MAX_GAP_FILL_FRAMES):
    out = p3ds.copy()
    frames = np.arange(len(p3ds))

    for lm in range(p3ds.shape[1]):
        missing = np.isnan(p3ds[:, lm]).any(axis=1)
        if missing.all() or not missing.any():
            continue

        # find each run of missing frames and fill it only if it is short and has data on both sides
        starts = np.flatnonzero(missing & ~np.r_[False, missing[:-1]])
        ends = np.flatnonzero(missing & ~np.r_[missing[1:], False]) + 1
        known = ~missing
        for s, e in zip(starts, ends):
            if e - s > max_gap or s == 0 or e == len(p3ds):
                continue
            for axis in range(3):
                out[s:e, lm, axis] = np.interp(frames[s:e], frames[known], p3ds[known, lm, axis])

    return out


# function to low-pass each landmark's trajectory with a Savitzky-Golay filter
#   small window so fast motion such as a punch survives
#   runs between gaps shorter than the window are left as they are
def smooth(p3ds, window=config.SMOOTH_WINDOW_FRAMES, polyorder=config.SMOOTH_POLYORDER):
    out = p3ds.copy()

    for lm in range(p3ds.shape[1]):
        present = ~np.isnan(p3ds[:, lm]).any(axis=1)

        # smooth each continuous run of frames on its own, so NaN gaps don't spread
        starts = np.flatnonzero(present & ~np.r_[False, present[:-1]])
        ends = np.flatnonzero(present & ~np.r_[present[1:], False]) + 1
        for s, e in zip(starts, ends):
            if e - s >= window:
                out[s:e, lm] = savgol_filter(p3ds[s:e, lm], window, polyorder, axis=0)

    return out
