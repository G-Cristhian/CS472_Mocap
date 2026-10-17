# Processing a take

What to do with the videos after a session: from files on the laptop to a skeleton you can watch and numbers you can compare. The pipeline reference is `backend/mocap_pipeline/README.md`; this is the order to do things in and what to write down.

Before this: the files are off the phones as originals and `check_videos` passed on them ([filming.md](filming.md), sections 8 and 9).

## 1. One folder per take, in and out

Inputs are already one folder per take with the camera number in the file name (filming.md, section 8). Outputs follow the same rule: every take gets its own output folder with its own calibration file, so takes never reuse each other's calibration by accident[^1].

```
backend/output/
  take01/   out3d.json  out3d.bvh  calibration.json  out3d.metrics.json  out3d.log  ...
  take02/   ...
```

`backend/output/` is ignored by git. Copy the folder somewhere shared when the session is done.

## 2. Detect first, while the files are fresh

Detection is the slow stage, minutes per camera, and it never needs redoing.[^2] Run it for every take as soon as the files are on the laptop, and stop there:

```
cd backend
source .venv/bin/activate
python -m mocap_pipeline.run_pipeline ../session/take01/*.MOV ../session/take01/*.mp4 \
    --height-m 1.78 --out output/take01/out3d.json --calibration output/take01/calibration.json \
    --stop-after keypoints
```

List the videos in camera order, camera 0 first. The `*.MOV *.mp4` globs sort by name, which is why the file names start with the camera number.[^3] Give the performer's height from the take log. Non-iPhone cameras also need `--fov` (the Fold is about 75).[^4]

This writes one `out3d.keypoints.<camera>.npz` per video. Everything after this is seconds.

## 3. Finish the run

```
python -m mocap_pipeline.run_pipeline ../session/take01/*.MOV ../session/take01/*.mp4 \
    --height-m 1.78 --out output/take01/out3d.json --calibration output/take01/calibration.json \
    --resume
```

`--resume` reuses the keypoints and runs sync, calibration, triangulation, smoothing and the BVH.[^5] If it stops with a message, the table in filming.md section 11 says what it means and what to do; fix and rerun with `--resume` again.

## 4. Read the numbers before you watch

Open `output/take01/out3d.metrics.json`. Four numbers say whether the take is good; write them in the session log for every take:

| Key | Good | Means trouble |
|---|---|---|
| `calibrate.reprojection_error_px` (per camera) | under 3 px |[^6] one camera much higher than the others: it moved, or its `--fov` is wrong |
| `rig.bone_lengths.mean_std_m` | under 0.01 m |[^7] over 0.02 m: noisy joints or a bad calibration |
| `pose_final.missing_fraction` | under 0.05 |[^8] high on one joint (`missing_fraction_per_joint`): hidden from all but one camera |
| `scale.upright_frames` | 30 or more |[^9] near the minimum of 10: the height pose was short, the scale may be off |

Also useful: `sync.cross_check` (a shift over 50 ms with `applied: false` means the clap was doubtful[^10]; check it by eye), `triangulate.views_dropped` (how often a camera disagreed), `timing` (seconds per stage). Every key is explained in the pipeline README, section Metrics.

## 5. Watch it

Open `output/take01/out3d.bvh` in the frontend viewer (`cd frontend && npm run dev`, open a project, "Open .bvh / .json") or in Blender. The skeleton should stand on the floor, face the viewer, and move like the take. Look at the fast moments: a wrist on a punch, a foot on a kick. Jitter, a lagging joint, or a joint that disappears are what the numbers above should have warned about.

## 6. Reruns that are worth doing

All of these take seconds with `--resume`:

- `--no-smooth` to see the raw triangulation.
- `--recalibrate` after changing `--fov` or `--max-error`.
- A camera subset: the same take with fewer videos and a different `--out` and `--calibration` folder. Camera 0 must stay in the list.[^11]
- Another detector: see [comparing-pose-models.md](comparing-pose-models.md).

## 7. What to keep

For each take: the input folder, the output folder, and one line in the session log with the four numbers from step 4 and a word on how it looked. That line is what the field test report is built from.

---
## Sources

[^1]: The pipeline reuses an existing `--calibration` file unless `--recalibrate` is given (`run_pipeline.py`, README "Running"). Issue #16 proposes making a per-take calibration the default.
[^2]: README "Rerunning and debugging": a full run takes minutes, a `--resume` run seconds. Keypoints are reused when the video's size and modification time and the detector name match (`io.fingerprint_matches`, D-023).
[^3]: POSIX shells expand globs in sorted order (bash manual, Filename Expansion; zsh does the same), and the file naming in filming.md section 8 puts the camera number first.
[^4]: iPhone focal lengths come from the file's metadata; anything else uses `--fov` with default `DEFAULT_HFOV_DEG = 65` (`config.py`). 75 is the Fold estimate from filming.md section 3.
[^5]: `run_pipeline.run`: with `--resume`, the saved sync file supplies the clap times, triangulation is skipped only if the pose file is newer than its inputs, and smoothing and the BVH always run.
[^6]: The synthetic benchmark with realistic noise gives 1 to 3 px (`tests/evaluate_synthetic.py`); `CALIB_MAX_ERROR_PX = 10` is where the pipeline gives up (D-015). Reprojection error as the calibration quality measure: Zhang 2000, DOI 10.1109/34.888718.
[^7]: Limb-length variability as the precision measure without ground truth: Karashchuk et al., "Anipose: A toolkit for robust markerless 3D pose estimation", *Cell Reports* 36(13), 2021, DOI 10.1016/j.celrep.2021.109730. The synthetic test accepts under 0.02 m with realistic noise; 0.01 m is the target for real footage and is team judgement until the first session.
[^8]: `tests/test_metrics.py` requires under 0.05 on the synthetic scene with 2% dropout; a joint needs `MIN_CAMERAS_PER_JOINT = 2` views (`config.py`), and gaps over `MAX_GAP_FILL_FRAMES = 10` stay missing (D-016).
[^9]: `MIN_UPRIGHT_FRAMES = 10` (`config.py`, D-012) is the pipeline's minimum; 30 frames is one second of the three-second height pose and is team judgement.
[^10]: Corrected while adding these notes: the cross-check is rejected above `CLAP_MAX_REFINE_S = 0.05`, so `applied: false` means a shift over 50 ms, not 20 (`config.py`, `sync._refine_against_reference`). The metric records the shift either way.
[^11]: Camera 0 is the reference frame for the calibration and the world (`schemas.py`, D-013); a calibration file is only reused when its camera count matches (`run_pipeline.py`).
