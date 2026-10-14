# Multi-camera 3D landmarks
Runs MediaPipe on a video from each of 2 to 4 cameras, calibrates the cameras, and triangulates the 33 pose landmarks into 3D (meters).

Calibration uses the person's own landmarks by default. A printed ChArUco board is the fallback, kept in its own file (`board_calibration.py`) and only loaded when the person method fails.

---
# Files
- `main.py`: runs the whole pipeline
- `extract_2d.py`: MediaPipe on each video, landmarks in pixels, and matching frames across cameras
- `calibrate_person.py`: default calibration from the person's landmarks
- `board_calibration.py`: fallback calibration from a ChArUco board
- `iphone_camera.py`: iPhone-only, detects iPhone videos and reads each lens's focal length from the video metadata
- `triangulate.py`: 2D from all cameras to 3D, plus JSON output
- `smooth.py`: fills short gaps and removes jitter from the 3D landmarks
- `config.py`: every tunable number (confidence thresholds, calibration joints, smoothing), names match `backend/mocap_pipeline/config.py`

---
# Requirements
```
$ cd backend  # from the repository root
$ ./setup.sh  # installs backend/requirements.txt
$ source .venv/bin/activate
$ cd multicam_3d
```
On Linux without a desktop, MediaPipe also needs `libegl1` (`sudo apt install libegl1`).

The MediaPipe model defaults to the one the repo ships in `backend/landmarks_from_image_test/models/`. To use another, put `MODEL_FILEPATH=...pose_landmarker_heavy.task` in a `.env` file, or pass `--model`.

---
# How this maps to the team pipeline outline (`backend/mocap_pipeline`)
| Outline stage | Here |
|---|---|
| stage1 `detect.py` (2D joints, real timestamps, rotation flag, NaN for missing) | `extract_2d.py` |
| stage2 `sync.py` (clap, shared clock) | `extract_2d.stack_cameras_by_time` / `stack_cameras`, clap time given by hand with `--sync` |
| stage2 `calibrate.py` (calibration from the performer's joints) | `calibrate_person.py`, plus `board_calibration.py` as a fallback |
| stage2 `scale_floor.py` | scale from one measured body length (`--scale`); no floor or Y-up yet |
| stage2 `triangulate.py` (2+ cameras, confidence, drop one bad view) | `triangulate.py` |
| stage2 `smooth.py` (fill gaps up to 10 frames, low-pass) | `smooth.py` |
| stage3 rig / BVH, placement tool | not here yet |

Like the outline, calibration only uses the 12 stable body joints (shoulders to ankles) seen with at least 0.8 confidence, and triangulation ignores views below 0.5.

---
# Camera setup: front arc
Use 2, 3 or 4 cameras in an arc in front of the person, all facing them. Every camera must see the person's front, so no cameras behind or beside them.
- 2 cameras: about -35 and +35 degrees (60-90 degrees apart). A small angle gives poor depth.
- 3 cameras: about -60, 0 and +60 degrees.
- 4 cameras: about -65, -20, +20 and +65 degrees.
- Cameras at chest height, 2-4 m from the middle of the space, each seeing the whole body.
- Spread the cameras out. The outer cameras do most of the depth work, so don't bunch them in the middle.

More cameras means fewer lost landmarks: each landmark only needs any 2 cameras to see it, so an arm hidden from one side is usually still seen from another. If one camera mis-detects a landmark, the other cameras outvote it.

---
# Recording
- Clap at the start so the videos can be lined up (see Syncing below).
- For person calibration, start each session with ~10 seconds of the person walking around the space, turning toward each camera, and raising their arms. Standing still is not enough, and every camera needs to see this.
- Measure one body length on the subject for `--scale` (shoulder width by default).
- For non-iPhone cameras, know each camera's horizontal field of view for `--fov` (phone and webcam specs list it). A wrong value skews 3D lengths by a few cm without raising the error, so this matters.

Cameras can be mixed (e.g. 2 iPhones and 2 webcams). Each video is detected automatically:
- **iPhone**: the focal length is read from the video, `--fov` isn't needed. Use the original .MOV files (AirDrop or cable, not re-exported or sent through a messaging app, which strips the metadata). Check a file with `python iphone_camera.py IMG_1234.MOV`.
- **Anything else** (webcam, Android, etc.): uses `--fov`, one value for all or one per camera.

`--camera` overrides the detection, one value for all or one per video: `auto` (default), `iphone` or `webcam`. If a video said to be an iPhone has no focal length metadata, it says so and falls back to `--fov` for that camera.

iPhone recording settings, the same on every phone:
- Same resolution and frame rate (e.g. 1080p at 30 fps).
- Turn off Auto FPS / Auto Low Light FPS, Enhanced Stabilization, Action Mode and HDR Video (Settings > Camera > Record Video).
- Use the 1x lens, don't zoom or switch lenses while recording.
- Lock focus and exposure (press and hold on the subject until AE/AF LOCK shows).

---
# Syncing
- **Any iPhone in the setup**: iPhones record at a variable frame rate, and mixed cameras rarely share an exact frame rate, so all videos are matched by each frame's real timestamp. Pass the time of the clap in each video in seconds with `--sync`, one per camera. The camera with the lowest frame rate sets the output frames, and a frame with no match within half a frame in another video (a dropped frame) is left out for that camera. `"t"` in `out3d.json` is the real time, 0 at the clap.
- **Webcams only**: frames are matched by number. Use the same frame rate on every camera and `--offsets` (frames to skip at the start of each video, one per camera) to line them up.

---
# Running
```
$ uv run main.py cam0.mp4 cam1.mp4 --scale LEFT_SHOULDER RIGHT_SHOULDER 0.36 --fov 65
```
Four iPhones:
```
$ uv run main.py cam0.MOV cam1.MOV cam2.MOV cam3.MOV --sync 1.25 0.80 1.10 0.95
```
Mixed, two iPhones and two webcams with different lenses (`--fov` is only used for the webcams):
```
$ uv run main.py cam0.MOV cam1.mp4 cam2.mp4 cam3.MOV --fov 65 70 78 65 --sync 1.25 0.40 0.62 0.95
```

This saves `calibration.toml` and `out3d.json`. The calibration is reused next run; add `--recalibrate` if a camera moved or the number of cameras changed.

If person calibration fails (too little movement, or error above `--max-error`), it stops and asks for board videos. Then:
```
$ uv run board_calibration.py make-board board.png      # print at 100% scale, 300 dpi, landscape
$ uv run main.py cam0.mp4 cam1.mp4 cam2.mp4 --recalibrate --charuco-videos cam0_board.mp4 cam1_board.mp4 cam2_board.mp4
```
Film the board with every camera (one board video per camera), moving it around where neighbouring cameras can see it at the same time. Measure a printed square; if it isn't 3.0 cm, pass the real size by running `board_calibration.py calibrate ... --square-length` directly.

---
# Output
`out3d.json` is a list of frames:
```
[{"t": 0.0, "landmarks": {"NOSE": {"x": 0.12, "y": -0.65, "z": 3.1}, "LEFT_EYE_INNER": null, ...}}, ...]
```
Meters, in camera 0's frame (x right, y down, z away from camera 0). `null` means fewer than 2 cameras saw the landmark in that frame (or the views didn't agree), for longer than the 10 frames that get filled in.

Gaps of up to 10 frames are filled in and every landmark is lightly smoothed (Savitzky-Golay, 7 frames). Add `--no-smooth` for the raw triangulated points.
