<!-- Copied from: legacy/multicam_3d/README.md, updated for the mocap_pipeline layout -->
# mocap_pipeline
The team's outline with stages 1 and 2 filled in from our first multi-camera pipeline (now `backend/legacy/multicam_3d`, kept for reference): same folders, function names and data shapes (`schemas.py`). Each file starts with a comment saying which `multicam_3d` file it was copied from.

Videos from 2 or more cameras (iPhones and webcams can be mixed), each starting with a clap, go in. 3D joints per frame come out, in metres, Y up, floor at Y = 0.

New to the code? [docs/backend-outline.md](../../docs/backend-outline.md) walks through every step, file and function in plain language.

---
# Running
```
$ cd backend
$ python -m pip install -r mocap_pipeline/requirements.txt
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV cam2.mp4 --height-m 1.75
```
On Linux without a desktop, MediaPipe also needs the GL libraries: `sudo apt install libegl1 libgles2 libgl1`.

The MediaPipe model defaults to the one in `backend/models/`. `MODEL_FILEPATH` in a `.env` file or `--model` overrides it.

Results go to `backend/output/` (created automatically, ignored by git), wherever you run the command from: the 3D joints to `out3d.json`, the skeleton animation to `out3d.bvh` (same name as the JSON, `--no-bvh` to skip it) and the calibration to `calibration.json`. `--out take01.json` / `--calibration ...` save somewhere else instead (missing folders are created).

The calibration is reused on the next run; add `--recalibrate` if a camera moved or the number of cameras changed.

## Choosing the pose model
`--detector mediapipe|rtmpose` picks the stage 1 model (default `mediapipe`). Each model lives in `stage1_keypoints/backends.py` and fills the same 33 MediaPipe joints, so stages 2 and 3 do not change.

- `mediapipe`: MediaPipe PoseLandmarker (heavy), tracks the performer between frames.
- `rtmpose`: RTMPose with the Halpe-26 (body with feet) model, via `rtmlib`. A person detector runs every frame and the largest person is taken as the performer. Fills 21 of the 33 joints, every one stages 2 and 3 use (eye corners, mouth and fingers stay empty; the foot tip comes from the big toe). The models download on the first run, to `~/.cache/rtmlib`; `--model` is not used.

To compare models on the same take, give each its own output and calibration, so neither reuses the other's:
```
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --height-m 1.75 --out output/mp/out3d.json --calibration output/mp/calibration.json
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --height-m 1.75 --detector rtmpose --out output/rtm/out3d.json --calibration output/rtm/calibration.json
```

## Choosing the smoother
`--smoother savgol|butterworth` picks the stage 2c filter that removes jitter from the 3D joints (default `savgol`). Both live in `stage2_reconstruct/smooth.py`; the constants are in `config.py`.

- `savgol`: Savitzky-Golay, a quadratic fitted through each 7-frame window. Keeps the shape of a fast peak such as a punch.
- `butterworth`: a zero-phase Butterworth low-pass at `BUTTER_CUTOFF_HZ` (8 Hz), order 2 run forward and backward. The biomechanics standard; it has a true cutoff frequency, which Savitzky-Golay does not.

Smoothing always runs, even with `--resume`, so comparing them on one take costs seconds and uses the same triangulation. Rename `out3d.json` and `out3d.bvh` between the two runs, or they overwrite:
```
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --height-m 1.75 --out output/take01/out3d.json
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --height-m 1.75 --out output/take01/out3d.json --resume --smoother butterworth
```
`out3d.metrics.json` records the smoother under `run.smoother` and `smooth`, and `pose_raw` and `pose_final` each carry `jitter_mm`, the mean frame-to-frame second difference of joint position: compare it between the two runs, and look at the fast moments in the viewer. `python -m tests.evaluate_synthetic` prints the same comparison against a known truth.

---
# Rerunning and debugging
Every stage saves its result next to the `--out` file, named after it. For the default `out3d.json`:

| File | Stage | What is in it |
|---|---|---|
| `out3d.keypoints.<camera>.npz` | 1 | one per camera: raw 2D joints, confidence and frame times, plus a fingerprint of the source video |
| `out3d.sync.json` | 2a | the clap time in each video and the shared 30 fps timeline |
| `calibration.json` | 2b | the cameras (already reused on the next run, see above) |
| `out3d.pose.npz` | 2c | the 3D joints before smoothing |
| `out3d.metrics.json` | all | quality numbers for the run, see Metrics below |
| `out3d.log` | all | everything the run printed, time-stamped |

`--resume` loads these instead of recomputing: detection is skipped for a video whose keypoints file exists, whose video has not changed (size and modification time are checked) and which was made with the same `--detector`, the clap search is skipped when the sync file exists, and triangulation is skipped when the pose file is newer than the calibration, sync and keypoints files. Smoothing and the `.bvh` always run, so tuning them is a quick `--resume` away:
```
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --height-m 1.75            # full run, minutes
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --resume --no-smooth       # seconds
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --resume --smoother butterworth   # the other filter
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --resume --recalibrate     # redo calibration only
```
`--sync` given by hand wins over the saved clap times; a changed `calibration.json` makes the pose file stale automatically.

`--stop-after keypoints|sync|calibrate|triangulate` runs up to that stage, writes its file and stops, so one person can hand another the data for the next stage without sharing the videos. The files load with `mocap_pipeline.io` (`load_keypoints`, `load_sync`, `load_rig`, `load_pose3d`).

Tests (no videos or model needed): `cd backend && python -m pytest tests`. Stages 2 and 3 are checked against a synthetic performer with exactly known joints, seen by virtual phones in the protocol's camera arc (`tests/synthetic_scene.py`); `python -m tests.evaluate_synthetic` prints the error of every stage for several camera layouts and noise levels, and `--bvh out.bvh` writes the result for the viewer.

---
# Metrics
Every run writes `out3d.metrics.json` (next to `--out`, also when the run fails or stops early) with the numbers that say how well the setup worked, and `out3d.log` with everything printed. There is no ground truth in the field, so these are precision and self-consistency measures, the ones the literature uses when truth is absent: reprojection error (Zhang 2000, DOI 10.1109/34.888718; Triggs et al. 1999, DOI 10.1007/3-540-44480-7_21) and limb-length variability (Karashchuk et al. 2021, DOI 10.1016/j.celrep.2021.109730). The synthetic tests add MPJPE against the truth (Ionescu et al. 2014, DOI 10.1109/TPAMI.2013.248).

| Key | What it says |
|---|---|
| `stage1.<camera>` | frames, fraction with no person, mean confidence overall and per joint |
| `sync` | clap time per camera, where the times came from, cross-check shift per camera in ms and whether it was applied |
| `calibrate` | starting pair, distinct correspondences per pair (how much the performer moved), reprojection error per camera, camera types, board fallback |
| `scale`, `floor` | upright frames, metres per unit, floor fit residual and spread, tilt from the body's up direction, whether the fitted plane was trusted |
| `triangulate` | mean reprojection error overall and per joint, views dropped as outliers, joints failed, joints with fewer than 2 views |
| `smooth.gaps` | gaps filled and gaps left missing |
| `pose_raw`, `pose_final` | missing fraction overall and per joint, mean cameras per joint, before and after smoothing |
| `rig.bone_lengths` | per bone: median length, standard deviation over the take and as a fraction; the cleanest precision number without ground truth |
| `timing` | seconds per stage and total |

Reading it: calibration error under about 3 px and bone-length standard deviation under about 1 cm mean the setup worked. A camera with a much higher reprojection error than the others moved or has the wrong field of view. A high missing fraction on one joint means that joint was hidden from all but one camera. The API serves the file at `GET /takes/<id>/metrics.json`.

---
# Recording a session
How to set up the phones, the room and the performer, and what to record, is in [`docs/procedures/filming.md`](../../docs/procedures/filming.md), and what to do with the files afterwards in [`docs/procedures/processing-a-take.md`](../../docs/procedures/processing-a-take.md). Before leaving the venue, check the files of each take (resolution, frame rate, audio, iPhone lens metadata, clap found) with
```
$ python -m mocap_pipeline.check_videos take01/*
```
It takes seconds and says which files the pipeline cannot use.

---
# Stages
| Stage | File | What it does |
|---|---|---|
| 1 | `stage1_keypoints/detect.py` | pose model (`backends.py`, `--detector`) on every frame: pixel joints, confidence, real frame times |
| 2a | `stage2_reconstruct/sync.py` | finds the clap in each video's audio, puts all cameras on one 30 fps timeline |
| 2b | `stage2_reconstruct/calibrate.py` | camera positions from the performer's joints (ours, not Liu et al.) |
| 2b | `stage2_reconstruct/board_calibration.py` | ChArUco board fallback if the above fails |
| 2b | `stage2_reconstruct/iphone_camera.py` | iPhone lens focal length from the video metadata |
| 2b | `stage2_reconstruct/scale_floor.py` | metres from the performer's height, floor at Y = 0, Y up |
| 2c | `stage2_reconstruct/triangulate.py` | 3D joints from every camera that saw them, drops one bad view |
| 2c | `stage2_reconstruct/smooth.py` | fills gaps up to 10 frames, light smoothing |
| 3a | `stage3_rig/skeleton.py` | 33 MediaPipe joints to the 17-joint H36M skeleton, fixed bone lengths, T-pose |
| 3b | `stage3_rig/rotations.py` | each joint's rotation per frame |
| 3c | `stage3_rig/bvh_writer.py` | writes the .bvh |
| - | `placement/` | camera placement tool: scores a rig's coverage (`metric.py`) and searches for a layout by simulated annealing (`anneal.py`), Rahimian & Kearney 2015 |

All tunable numbers are in `config.py`.

---
# Camera setup: front arc
- Any number from 2 up. Spread them evenly across an arc of up to about 130 degrees centred on the performer's front, so the outermost pair is 70 to 130 degrees apart. Examples: 2 cameras at -35 and +35; 3 at -60, 0, +60; 4 at -65, -20, +20, +65; 6 at -65, -40, -15, +15, +40, +65.
- More cameras means fewer lost joints, not more accuracy per joint: each joint needs any 2 cameras to see it, and the outermost pair does most of the depth work. Every extra camera costs its own detection time.
- Chest height, 2-4 m from the middle of the space, each seeing the whole body. Don't bunch the cameras in the middle.
- Every camera must see the performer's front (no cameras behind or beside them).

Each video is detected automatically: an **iPhone** video's focal length is read from its metadata (use the original .MOV files, AirDrop or cable, not re-exported or sent through a messaging app). **Anything else** uses `--fov` (horizontal field of view in degrees, one for all or one per camera). `--camera auto|iphone|webcam` overrides the detection.

iPhone settings, the same on every phone: same resolution and frame rate; Auto FPS / Auto Low Light FPS, Enhanced Stabilization, Action Mode and HDR Video off; 1x lens; focus and exposure locked.

---
# Recording
1. Start all cameras, then **clap once, sharply**, close enough that every phone hears it. Keep talking and music down at that moment: the clap must be clearly louder than anything else going on, or it won't be found.
2. **Right after the clap, stand still, upright, facing the cameras for a couple of seconds**: this measures the performer's height (sets the scale). This step is required: the run stops with "only N frames with the performer standing upright" if it is skipped, e.g. when a take starts straight in a fighting stance.
3. Walk around the space for ~10 seconds, turning towards each camera and raising the arms (calibrates the cameras). Make sure the feet are seen on the floor (finds the floor).
4. Perform.

If a clap can't be found (no audio track, or no sharp loud sound in the first 10 s), it stops and says so. Then give the clap time in each video by hand, in seconds: `--sync 1.25 0.80 1.10`.

If calibration from the performer fails (too little movement, or error above `--max-error`), it stops and asks for board videos:
```
$ python mocap_pipeline/stage2_reconstruct/board_calibration.py make-board board.png      # print at 100% scale, 300 dpi
$ python -m mocap_pipeline.run_pipeline cam0.mp4 cam1.mp4 --height-m 1.75 --recalibrate --charuco-videos cam0_board.mp4 cam1_board.mp4
```

---
# Output
`backend/output/out3d.json` (or the `--out` path) is a list of frames on the shared 30 fps timeline:
```
[{"t": 0.0, "landmarks": {"NOSE": {"x": 0.12, "y": 1.62, "z": -0.3}, "LEFT_EYE_INNER": null, ...}}, ...]
```
`t` is seconds after the clap. Metres; Y up with the floor at Y = 0; Z points from the performer towards camera 0; X is to the right as seen from camera 0; the origin is on the floor in the middle of where the performer walked. `null` means fewer than 2 cameras saw the joint (for longer than the 10 frames that get filled in).

---
# Skeleton animation (.bvh)
The `.bvh` holds the 17-joint Human3.6M (H36M) skeleton: Hip (root), hips, knees, ankles, Spine, Thorax, Neck, Head, shoulders, elbows, wrists. Centimetres, Y up, character facing +Z; rotation channels Z X Y. It opens in Blender (File > Import > Motion Capture (.bvh)) and three.js's BVHLoader (the frontend viewer).

- MediaPipe has no spine, neck or top of head, so they are approximated (see `joints.RIG_JOINT_SOURCES`): Spine halfway between hips and shoulders, Neck halfway between shoulders and ears, Head 2/3 of the shoulder-to-ear distance above the ears.
- Bone lengths are fixed for the whole take: the median over all frames, left and right averaged.
- Frames where a joint is missing are filled from the neighbouring frames.
- Twist along a limb can't be measured from joint positions, so arm twist follows the body's up direction and leg twist the hip line.

Stage 3 is based on [video2bvh](https://github.com/KevinLTT/video2bvh) (`bvh_skeleton/h36m_skeleton.py`, `bvh_helper.py`, `math3d.py`), MIT License, Copyright (c) 2020 KevinLTT. Its skeleton, bone-length rules, per-joint orientation rules and BVH writer were adapted to our Y-up data, with the rotation maths done by scipy. The license text is in the header of each `stage3_rig` file.

