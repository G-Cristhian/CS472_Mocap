<!-- Copied from: multicam_3d/README.md, updated for the mocap_pipeline layout -->
# mocap_pipeline
The team's outline with stages 1 and 2 filled in from our multi-camera pipeline (`backend/multicam_3d`): same folders, function names and data shapes (`schemas.py`). Each file starts with a comment saying which `multicam_3d` file it was copied from.

Videos from 2 to 4 cameras (iPhones and webcams can be mixed), each starting with a clap, go in. 3D joints per frame come out, in metres, Y up, floor at Y = 0.

---
# Running
```
$ cd backend
$ python -m pip install -r mocap_pipeline/requirements.txt
$ python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV cam2.mp4 --height-m 1.75 --out take01.json
```
On Linux without a desktop, MediaPipe also needs `libegl1` (`sudo apt install libegl1`).

The MediaPipe model defaults to the one in `backend/landmarks_from_image_test/models/`. `MODEL_FILEPATH` in a `.env` file or `--model` overrides it.

The calibration is saved to `calibration.json` and reused on the next run; add `--recalibrate` if a camera moved or the number of cameras changed.

---
# Stages
| Stage | File | What it does |
|---|---|---|
| 1 | `stage1_keypoints/detect.py` | MediaPipe on every frame: pixel joints, confidence, real frame times |
| 2a | `stage2_reconstruct/sync.py` | finds the clap in each video's audio, puts all cameras on one 30 fps timeline |
| 2b | `stage2_reconstruct/calibrate.py` | camera positions from the performer's joints (ours, not Liu et al.) |
| 2b | `stage2_reconstruct/board_calibration.py` | ChArUco board fallback if the above fails |
| 2b | `stage2_reconstruct/iphone_camera.py` | iPhone lens focal length from the video metadata |
| 2b | `stage2_reconstruct/scale_floor.py` | metres from the performer's height, floor at Y = 0, Y up |
| 2c | `stage2_reconstruct/triangulate.py` | 3D joints from every camera that saw them, drops one bad view |
| 2c | `stage2_reconstruct/smooth.py` | fills gaps up to 10 frames, light smoothing |
| 3 | `stage3_rig/` | skeleton and BVH: still the outline's placeholders |
| - | `placement/` | camera placement tool: still the outline's placeholders |

All tunable numbers are in `config.py`.

---
# Camera setup: front arc
- 2 cameras: about -35 and +35 degrees. 3 cameras: about -60, 0, +60. 4 cameras: about -65, -20, +20, +65.
- Chest height, 2-4 m from the middle of the space, each seeing the whole body. Don't bunch the cameras in the middle.
- Every camera must see the performer's front (no cameras behind or beside them).

Each video is detected automatically: an **iPhone** video's focal length is read from its metadata (use the original .MOV files, AirDrop or cable, not re-exported or sent through a messaging app). **Anything else** uses `--fov` (horizontal field of view in degrees, one for all or one per camera). `--camera auto|iphone|webcam` overrides the detection.

iPhone settings, the same on every phone: same resolution and frame rate; Auto FPS / Auto Low Light FPS, Enhanced Stabilization, Action Mode and HDR Video off; 1x lens; focus and exposure locked.

---
# Recording
1. Start all cameras, then **clap once, sharply**, close enough that every phone hears it. Keep talking and music down at that moment: the clap must be clearly louder than anything else going on, or it won't be found.
2. **Stand still, upright, facing the cameras for a couple of seconds**: this measures the performer's height (sets the scale).
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
The `--out` JSON is a list of frames on the shared 30 fps timeline:
```
[{"t": 0.0, "landmarks": {"NOSE": {"x": 0.12, "y": 1.62, "z": -0.3}, "LEFT_EYE_INNER": null, ...}}, ...]
```
`t` is seconds after the clap. Metres; Y up with the floor at Y = 0; Z points from the performer towards camera 0; X is to the right as seen from camera 0; the origin is on the floor in the middle of where the performer walked. `null` means fewer than 2 cameras saw the joint (for longer than the 10 frames that get filled in).
