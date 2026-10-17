# Processing a take

What to do with the videos after a session: from files on the laptop to a skeleton you can watch and numbers you can compare. The pipeline reference is `backend/mocap_pipeline/README.md`; this is the order to do things in and what to write down.

Before this: the files are off the phones as originals and `check_videos` passed on them ([filming.md](filming.md), sections 8 and 9).

## 1. One folder per take, in and out

Inputs are already one folder per take with the camera number in the file name (filming.md, section 8). Outputs follow the same rule: every take gets its own output folder with its own calibration file, so takes never reuse each other's calibration by accident.

```
backend/output/
  take01/   out3d.json  out3d.bvh  calibration.json  out3d.metrics.json  out3d.log  ...
  take02/   ...
```

`backend/output/` is ignored by git. Copy the folder somewhere shared when the session is done.

## 2. Detect first, while the files are fresh

Detection is the slow stage, minutes per camera, and it never needs redoing. Run it for every take as soon as the files are on the laptop, and stop there:

```
cd backend
source .venv/bin/activate
python -m mocap_pipeline.run_pipeline ../session/take01/*.MOV ../session/take01/*.mp4 \
    --height-m 1.78 --out output/take01/out3d.json --calibration output/take01/calibration.json \
    --stop-after keypoints
```

List the videos in camera order, camera 0 first. The `*.MOV *.mp4` globs sort by name, which is why the file names start with the camera number. Give the performer's height from the take log. Non-iPhone cameras also need `--fov` (the Fold is about 75).

This writes one `out3d.keypoints.<camera>.npz` per video. Everything after this is seconds.

## 3. Finish the run

```
python -m mocap_pipeline.run_pipeline ../session/take01/*.MOV ../session/take01/*.mp4 \
    --height-m 1.78 --out output/take01/out3d.json --calibration output/take01/calibration.json \
    --resume
```

`--resume` reuses the keypoints and runs sync, calibration, triangulation, smoothing and the BVH. If it stops with a message, the table in filming.md section 11 says what it means and what to do; fix and rerun with `--resume` again.

## 4. Read the numbers before you watch

Open `output/take01/out3d.metrics.json`. Four numbers say whether the take is good; write them in the session log for every take:

| Key | Good | Means trouble |
|---|---|---|
| `calibrate.reprojection_error_px` (per camera) | under 3 px | one camera much higher than the others: it moved, or its `--fov` is wrong |
| `rig.bone_lengths.mean_std_m` | under 0.01 m | over 0.02 m: noisy joints or a bad calibration |
| `pose_final.missing_fraction` | under 0.05 | high on one joint (`missing_fraction_per_joint`): hidden from all but one camera |
| `scale.upright_frames` | 30 or more | near the minimum of 10: the height pose was short, the scale may be off |

Also useful: `sync.cross_check` (a shift over 20 ms with `applied: false` means the clap was doubtful; check it by eye), `triangulate.views_dropped` (how often a camera disagreed), `timing` (seconds per stage). Every key is explained in the pipeline README, section Metrics.

## 5. Watch it

Open `output/take01/out3d.bvh` in the frontend viewer (`cd frontend && npm run dev`, open a project, "Open .bvh / .json") or in Blender. The skeleton should stand on the floor, face the viewer, and move like the take. Look at the fast moments: a wrist on a punch, a foot on a kick. Jitter, a lagging joint, or a joint that disappears are what the numbers above should have warned about.

## 6. Reruns that are worth doing

All of these take seconds with `--resume`:

- `--no-smooth` to see the raw triangulation.
- `--recalibrate` after changing `--fov` or `--max-error`.
- A camera subset: the same take with fewer videos and a different `--out` and `--calibration` folder. Camera 0 must stay in the list.
- Another detector: see [comparing-pose-models.md](comparing-pose-models.md).

## 7. What to keep

For each take: the input folder, the output folder, and one line in the session log with the four numbers from step 4 and a word on how it looked. That line is what the field test report is built from.
