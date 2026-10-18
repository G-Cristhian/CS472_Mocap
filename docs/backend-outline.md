# How the backend works, file by file

This is a plain-language map of everything under `backend/`. It is written for
someone who has never opened the code: what each step does, which file does it,
and what every function and class in that file takes, gives back, and does
inside. Read it top to bottom once, then use it as a reference.

If a word is unfamiliar, the glossary at the end explains it. Every term is
spelled out the first time it appears in a section.

The code itself is the final word. When this page and the code disagree, the
code is right and this page needs fixing. Line numbers are left out on purpose
so the page goes stale more slowly; search for the function name instead.

---

## 0. The big picture

**What the backend does.** You film one person with two or more phones at the
same time. Each video starts with a hand clap. The backend turns those videos
into a skeleton animation file that Blender or a game engine can play back.

**The steps, in order.** Each step reads the previous step's result and writes
its own. The results are small files saved next to the output, so a step can be
re-run on its own.

| Step | Plain description | Folder or file | Reads | Writes |
|---|---|---|---|---|
| 0 | Check the videos at the venue before leaving | `mocap_pipeline/check_videos.py` | the video files | a printed report |
| 1 | Find the 33 body landmarks in every frame of every video | `mocap_pipeline/stage1_keypoints/` | one video | one set of 2D landmarks per camera |
| 2a | Find the clap in each video and put all cameras on one shared clock | `mocap_pipeline/stage2_reconstruct/sync.py` | the 2D landmarks and the audio | a clock offset per camera, and the landmarks resampled onto the shared clock |
| 2b | Work out where each camera is and which way it points, from the performer's own body | `stage2_reconstruct/calibrate.py` plus `iphone_camera.py` and `board_calibration.py` | the synced 2D landmarks | a camera rig (lens numbers plus position and orientation per camera) |
| 2b, second half | Turn the rig's made-up units into metres, find the floor, point the up axis up | `stage2_reconstruct/scale_floor.py` | the rig and a rough 3D result | the rig in metres |
| 2c | Combine every camera's 2D landmarks into one 3D point per landmark per frame | `stage2_reconstruct/triangulate.py` | synced landmarks and the rig | 3D points, with holes where too few cameras saw a landmark |
| 2c, clean-up | Fill short holes and remove jitter | `stage2_reconstruct/smooth.py` | 3D points | cleaner 3D points |
| 3 | Turn loose 3D points into a skeleton with fixed bone lengths, work out each joint's rotation, write the animation file | `mocap_pipeline/stage3_rig/` | 3D points | a `.bvh` file |

**Three ways to start a run.** All three end up calling the same function,
`run()` in `run_pipeline.py`:

- the command line: `python -m mocap_pipeline.run_pipeline cam0.MOV cam1.MOV --height-m 1.75`
- the desktop tester app in `desktop/`, which builds that command and runs it
- the web API in `backend/api.py`, which accepts an upload and runs it in the background

**Five data shapes.** Steps hand each other five kinds of object, defined in
`schemas.py` and described in section 1. Everything else is internal to a step.

**One place for every tunable number.** Every threshold, window size and
default lives in `config.py`, never inside a step. If you want to change how
strict a check is, you change it there.

**What a run leaves on disk.** For an output path of `out3d.json`:

| File | Made by step | Contents |
|---|---|---|
| `out3d.keypoints.<camera>.npz` | 1 | that camera's raw 2D landmarks, confidences and frame times, plus a fingerprint of the video |
| `out3d.sync.json` | 2a | the clap time in each video and the shared timeline |
| `calibration.json` | 2b | the camera rig, reused on the next run |
| `out3d.pose.npz` | 2c | the 3D points before clean-up |
| `out3d.json` | 2c | the cleaned 3D points, one record per frame, for the web viewer |
| `out3d.bvh` | 3 | the skeleton animation |
| `out3d.metrics.json` | all | quality numbers from every step, and timings |
| `out3d.log` | all | everything the run printed, with timestamps |

---

## 1. Shared pieces, used by every step

### `mocap_pipeline/schemas.py`: the five data shapes

These are Python dataclasses: plain containers with named fields and no
behaviour. The conventions, which every step relies on:

- Arrays are numpy arrays. In the shapes below, F is the number of frames and J
  is the number of landmarks, which is 33.
- A missing value is NaN ("not a number"), never zero.
- 2D points are in pixels with the origin at the top-left of the image.
- 3D points are in metres once step 2b's second half has run, with Y pointing
  up and the floor at Y equals 0.
- Camera 0, the first video given, is the reference camera.

**`Keypoints2D`**, the output of step 1, one per camera.

| Field | Type | Meaning |
|---|---|---|
| `camera_id` | text | a stable name for the camera, normally the video's file name without its extension |
| `video_path` | text | where the video is |
| `width`, `height` | whole numbers | the frame size in pixels |
| `fps` | number | the frame rate the video file claims |
| `timestamps` | array, shape (F,) | the real time of each frame in seconds from the start of this video |
| `points` | array, shape (F, J, 2) | pixel x and y of each landmark in each frame |
| `confidence` | array, shape (F, J) | how sure the detector was, 0 to 1 |

**`SyncResult`**, the output of step 2a.

| Field | Type | Meaning |
|---|---|---|
| `clap_time_s` | dictionary, camera id to number | how many seconds into each video the clap happens |
| `common_timestamps` | array, shape (F_common,) | the shared timeline: time 0 is the clap, one entry per shared frame |

**`Camera`**, one calibrated camera. The model is a pinhole camera with no lens
distortion.

| Field | Type | Meaning |
|---|---|---|
| `camera_id` | text | as above |
| `K` | array, 3 by 3 | the lens numbers: focal length in pixels and the image centre (see glossary, "intrinsics") |
| `R` | array, 3 by 3 | a rotation that turns world directions into this camera's directions |
| `t` | array, shape (3,) | a translation that, together with R, moves world points into this camera's coordinates |

A world point X lands in the camera's coordinates as R times X plus t. The
camera's own position in the world is minus R transposed times t.

**`CameraRig`**, the output of step 2b.

| Field | Type | Meaning |
|---|---|---|
| `cameras` | list of `Camera` | every camera, in the order the videos were given |
| `reprojection_error_px` | dictionary, camera id to number | the calibration quality per camera: how far, on average, the landmarks land from where the calibrated camera predicts them, in pixels |
| `is_metric` | true or false | false until the rig has been converted to metres with Y up |

**`Pose3D`**, the output of step 2c and the input to step 3.

| Field | Type | Meaning |
|---|---|---|
| `fps` | number | the frame rate of this data |
| `points` | array, shape (F, J, 3) | x, y, z of each landmark in each frame |
| `num_views` | array, shape (F, J) | how many cameras contributed to each point; 0 means a hole |

### `mocap_pipeline/joints.py`: the landmark names and the skeleton

No functions, only named lists and dictionaries that every step imports.

- **`MEDIAPIPE_JOINTS`**: the 33 landmark names in the detector's own order,
  from NOSE through the eyes, ears, mouth, shoulders, elbows, wrists, hand
  points, hips, knees, ankles, heels, to the foot tips. Position in this list
  equals the index in every array. Never reorder it.
- **`NUM_JOINTS`**: 33. **`JOINT_INDEX`**: name to position, for looking up a
  landmark by name.
- **`CALIBRATION_JOINTS`**: the 12 landmarks stable enough to calibrate from:
  shoulders, elbows, wrists, hips, knees, ankles. Face and finger points jitter
  too much.
- **`RIG_JOINT_SOURCES`**: how each of the 17 skeleton joints is built from the
  33 landmarks. A list means "average these landmarks". A dictionary means "a
  weighted sum with these weights". The skeleton is the 17-joint one from the
  Human3.6M research dataset, as used by the video2bvh project. Three joints
  the detector does not have are approximated: Spine is halfway between the
  hip centre and the shoulder centre, Neck is halfway between the shoulder
  centre and the ear centre, and Head is the ear centre raised along the
  shoulders-to-ears line by two thirds of that distance.
- **`RIG_PARENTS`**: each skeleton joint's parent. Hip is the root with no
  parent. The order matters: a parent always comes before its children, which
  is what the animation file format needs.
- **`RIG_JOINTS`**: the 17 names in that order.
- **`RIG_END_SITES`**: skeleton joints written as an "end site" in the file, a
  position with no rotation of its own. Only Head.

### `mocap_pipeline/config.py`: every tunable number

No functions. Constants grouped by step, each with a comment saying what it
means and, where known, where the value came from. The decisions sheet
(`docs/decisions/DECISIONS.md`) records the reasoning for most of them. The
groups:

| Group | Constants |
|---|---|
| step 1 | the path to the pose model file |
| cameras | the minimum number of cameras, 2 |
| step 2a, sync | how many seconds of audio to search for the clap; the shared clock rate; the audio sample rate and the window, smoothing, loudness and rise-time thresholds that define a clap; the cross-check window; the longest hole the resampler bridges |
| step 2b, calibration | the minimum confidence for a landmark to count; the pixel tolerance for the camera-pair estimate; convergence settings for a method that is not used; the default field of view; the minimum number of shared points; the minimum points to place a further camera; the error above which the board fallback is used |
| step 2b, scale and floor | the skull-above-ears and heel-above-floor offsets; the upright test tolerance; the minimum upright frames; the fraction of lowest foot points used for the floor |
| step 2c, triangulation | the minimum confidence per camera; the minimum cameras per landmark; the longest gap filled; the reprojection error that drops a camera's view |
| step 2c, smoothing | the Savitzky-Golay window and polynomial order; which smoother is the default; the Butterworth cutoff and order |
| placement tool | the usable range of angles between two cameras; the camera's effective range; the penalty for an unseen point; the fallback grid; the maximum sample size |

### `mocap_pipeline/io.py`: saving and loading the data shapes

Every step's result can be written to disk and read back, so steps can be run
one at a time and teammates can hand each other sample data.

- **`stage_paths(out_path, camera_ids)`**. Takes the output path and the camera
  ids. Gives back a dictionary of file paths for every step's file, derived
  from the output path as in the table in section 0.
- **`video_fingerprint(video_path)`**. Takes a video path. Gives back its size
  in bytes and its modification time. Enough to notice a swapped or re-exported
  video.
- **`fingerprint_matches(saved, video_path)`**. True if a saved fingerprint
  still matches the file on disk. Any error counts as "does not match".
- **`save_keypoints(kp, path, fingerprint)`** and **`load_keypoints(path, with_fingerprint)`**.
  Write and read a `Keypoints2D` as a compressed numpy archive. Every field
  becomes one array in the archive; text and single numbers are stored as
  zero-dimensional arrays. The fingerprint of the source video is stored
  alongside as a JSON string, and the pipeline also stores which detector made
  the file, so a changed video or a different detector triggers re-detection.
- **`save_sync(sync, path)`** and **`load_sync(path)`**. The `SyncResult` as
  JSON, since it is small and people will want to open it.
- **`save_rig(rig, path)`** and **`load_rig(path)`**. The `CameraRig` as JSON,
  each camera's three arrays written as nested lists.
- **`save_pose3d(pose, path)`** and **`load_pose3d(path)`**. The `Pose3D` as a
  compressed numpy archive.
- **`save_pose3d_json(pose, path, timestamps)`**. The cleaned 3D points in the
  form the web viewer reads: a list with one record per frame, each holding
  the time in seconds from the clap and a dictionary from landmark name to x,
  y, z in metres, or null when the landmark is missing.

### `mocap_pipeline/metrics.py`: quality numbers and the run log

There is no ground truth in the field, so the numbers recorded are
self-consistency measures: how well the cameras agree with each other, how
stable the bone lengths are, how much the points jitter. The module keeps one
"open run" at a time in module-level variables and writes it out at the end.

- **`record(key, value)`**. Store one number, or a dictionary or list of
  numbers, under a dotted key such as `triangulate.views_dropped`. Dots become
  nesting in the JSON. Does nothing when no run is open, so every step works
  unchanged in tests. Numpy values are converted to plain Python values and
  NaN becomes null (`_clean` does that conversion).
- **`active()`**. True while a run is open.
- **`time(stage)`**. A context manager: wrap a block in it and the block's
  duration is recorded under `timing.<stage>_s`.
- **`keypoints_summary(kp)`**. Step 1 quality for one camera: frame count,
  nominal frame rate, the fraction of frames with nobody detected, and the
  mean confidence overall and per landmark.
- **`pose_summary(pose)`**. Step 2c coverage: frame count, the fraction of
  landmark-frames that are holes overall and per landmark, the mean number of
  cameras per point, and the jitter number below.
- **`jitter_mm(pts)`**. A smoothness measure: for each landmark, take its
  position in three consecutive frames and compute "next minus two times
  current plus previous", which is zero for steady motion and large for
  shaking. Average the size of that over every frame where all three are
  present, in millimetres. Real motion contributes too, so only compare it
  between runs of the same take.
- **`bone_length_summary(rig_positions, rig_joints, rig_parents)`**. Step 3
  precision: for each bone, the standard deviation of its length over the take
  and that as a fraction of its median. A real body has zero; what is left is
  detection noise plus calibration error.
- **`_Tee`** (class). Replaces standard output while a run is open: everything
  printed still appears on screen and is also written to the log file, each
  line stamped with the time.
- **`paths_for(out_path)`**. The metrics and log paths for an output path.
- **`start(out_path, **header)`**. Open a run: reset the numbers, record the
  header values (videos, detector, smoother, height, options) under `run`, and
  install the tee.
- **`finish(status, error)`**. Close the run: record the finish time and
  status, write the metrics file, restore standard output. Returns the path.
- **`finish_quietly()`**. Drop an open run without writing, used when a new
  run starts while one is open.
- **`load(out_path)`**. Read a metrics file back as a dictionary.

---

## 2. Step 0: checking the videos at the venue

### `mocap_pipeline/check_videos.py`

Run on the phone videos before the tripods come down. It takes seconds per
take because it never runs the pose detector. Problems print as WARNING (worth
a retake) or FAIL (the pipeline cannot use the file). The process exits with
code 1 if anything failed.

- **`video_info(path)`**. Opens the video with OpenCV and gives back width,
  height, frame rate and frame count, or a record saying it could not be
  opened.
- **`iphone_info(path)`**. The phone model, lens and 35 mm equivalent focal
  length if the file carries Apple's metadata, else None. Uses
  `iphone_camera.read_metadata`.
- **`clap_time(path)`**. The clap time in seconds using the same three
  functions step 2a uses, or None and the reason.
- **`check(video_paths)`**. For every video, prints the size, frame rate,
  length, lens information and clap time, with a warning if the frame rate is
  under 50, if a `.MOV` file lacks iPhone metadata (it was probably
  re-exported), or if the clap sits near the end of the search window. Then
  across cameras: warns if frame rates or resolutions differ, if lengths
  differ by more than 5 seconds, and runs the cross-check from step 2a to
  show the refined clap times. Returns 1 if any file failed.
- **`main()`**. Command-line wrapper around `check`.

---

## 3. Step 1: finding the landmarks in every frame

### `mocap_pipeline/stage1_keypoints/detect.py`: reading the video

- **`detect_video(video_path, model_path, detector)`**. Takes one video, the
  model file path, and the detector name. Gives back a `Keypoints2D`.
  1. Open the video with OpenCV. If it cannot be opened, raise an error.
  2. Read the claimed frame rate, falling back to 30 if the file reports none.
  3. Create the detector (section below) and loop over every frame in order.
  4. For each frame: note the frame's real time from the decoder (if the
     decoder gives zero for a frame after the first, fall back to frame index
     divided by frame rate); convert the frame from OpenCV's blue-green-red
     order to red-green-blue; hand it to the detector; append the 33 points
     and 33 confidences it returns.
  5. Every 30 frames, if the environment variable `MOCAP_PROGRESS` is set,
     print a progress line that the desktop tester reads.
  6. Never drop a frame: a frame with nobody in it gets NaN points and zero
     confidence, so the arrays stay aligned with the timestamps.
  7. Build the `Keypoints2D` with the camera id set to the file name stem, the
     width and height from the first decoded frame, and the arrays stacked.

### `mocap_pipeline/stage1_keypoints/backends.py`: the pose models

All models are hidden behind one small interface so the rest of the pipeline
never knows which one ran. A model turns one frame into 33 points and 33
confidences in the detector's standard order; landmarks a model does not
produce stay NaN with confidence 0.

- **`DEFAULT_BACKEND`**: the text `"mediapipe"`.
- **`empty_frame()`**. The result for a frame with nobody in it: 33 NaN points
  and 33 zeros.
- **`PoseBackend`** (class, the interface). Used as a context manager, meaning
  `with create_backend(...) as backend:`, so the model is released at the end.
  Its `detect(rgb, frame_ms)` method takes one frame and its time in
  milliseconds and returns points and confidences; the base class raises "not
  implemented" because each model overrides it. `close()` releases resources.
  Frames must be given in order, one video per instance, because some models
  track the person from frame to frame.
- **`MediaPipeBackend`** (class). Google's MediaPipe Pose Landmarker in video
  mode with one person. Built from a `.task` model file; raises if none is
  given. `detect` wraps the frame in a MediaPipe image, forces the timestamp
  to be strictly increasing (the model insists), runs it, and converts the
  model's 0-to-1 coordinates to pixels by multiplying by width and height.
  The confidence is the model's visibility score. The model's own depth guess
  is thrown away: step 2c computes real depth.
- **`HALPE26_JOINTS`** and **`MEDIAPIPE_FROM_HALPE26`**: the 26-landmark
  naming used by the second model and the mapping from our 33 names to it.
  The foot tip is approximated by the big toe.
- **`halpe26_to_mediapipe(keypoints, scores)`**. Takes one person's 26 points
  and scores. Gives back 33 points and confidences in our order, with the
  scores clipped to 0 to 1 and any landmark scored zero or less set to NaN.
- **`pick_person(bboxes)`**. Given the boxes of everyone detected, the index
  of the largest box, taken to be the performer; None if nobody.
- **`RTMPoseBackend`** (class). The RTMPose model through the rtmlib package,
  which downloads its own files on first use. It does not track: every frame
  a person detector finds everyone, `pick_person` chooses the largest, and
  the pose model runs on that person's box. With no box it returns an empty
  frame, because running the pose model on the whole image would always
  "find" someone.
- **`BACKENDS`**: dictionary from name to class. Adding a model means writing
  one class here and adding it to this dictionary.
- **`create_backend(name, model_path)`**. Look the name up and build the
  class, with a clear error naming the valid choices if the name is unknown.

---

## 4. Step 2a: putting every camera on one clock

### `mocap_pipeline/stage2_reconstruct/sync.py`

The phones were not started at the same instant. The clap is a sharp sound in
every recording, so finding it in each audio track tells us each camera's
offset. After this step, frame i means the same instant in every camera.

- **`ClapNotFoundError`** (class). Raised when no clear clap is found, so the
  user re-records or gives the times by hand rather than getting silently
  wrong 3D.
- **`_read_audio(video_path, max_seconds)`**. Decode the first `max_seconds`
  of the audio track with the PyAV library, resampled to mono at 16 kHz,
  as one float array. Raises `ClapNotFoundError` if the file has no audio.
- **`_loudness(audio)`**. The root-mean-square loudness every 2 milliseconds,
  each value averaged over a centred 10 millisecond span. The averaging stops
  the pitch of a voice from looking like a string of tiny claps. Uses a
  cumulative sum of squared samples so every window is one subtraction.
- **`_clap_from_loudness(rms, name)`**. Find the clap onset in a loudness
  curve. The idea: a clap goes from quiet to full loudness within a few
  milliseconds, while speech, music and footsteps ramp up slowly.
  1. Background level: the median loudness.
  2. For every moment, the loudest moment 30 to 100 milliseconds before it
     (the 30 millisecond gap skips the pre-echo that phone audio compression
     smears ahead of a sharp sound). The "rise" is the moment's loudness
     divided by that.
  3. Ignore moments not at least 8 times the background.
  4. Take the 200 strongest rises in order. For each, find the true peak
     within the next 100 milliseconds, then walk back from the peak to where
     the loudness was a quarter of the way up from what came before. If that
     took longer than 25 milliseconds it is not a clap; try the next.
  5. For the first that passes, the onset is the first moment within 10
     milliseconds before the peak that is at least halfway up. Return it in
     seconds. If none passes, raise with a message explaining the thresholds.
- **`find_clap_time(video_path)`**. The two functions above on one video.
- **`_refine_against_reference(rms_ref, clap_ref, rms, clap, name)`**. Cross
  check one camera's clap against camera 0's: take the loudness curve a
  quarter second either side of each clap, remove each curve's mean, slide one
  over the other to find the shift where they match best. If the shift is
  under 50 milliseconds, apply it; otherwise keep the detected clap and warn,
  because the match probably locked onto something else. Records the shift
  in the metrics.
- **`detect_claps(video_paths)`**. Clap time of every video, each refined
  against camera 0's.
- **`_resample(kp, times, common)`**. Put one camera's landmarks onto the
  shared timeline by straight-line interpolation between its two nearest
  frames. For each shared tick, find the camera frames just before and after,
  weight by where the tick falls between them, and blend both the points and
  the confidences. Two safety rules: if the two frames are more than 2.5 of
  this camera's frame intervals apart (the camera stalled), the tick becomes
  NaN with confidence 0 instead of a blend; and if either neighbour is NaN
  the result is NaN.
- **`synchronise(video_paths, keypoints, clap_times)`**. The whole step.
  1. Use the given clap times, or detect them.
  2. Shift each camera's timestamps so its clap is time 0.
  3. Build the shared timeline from 0 to the earliest end among cameras, at
     the shared clock rate from the configuration (30 per second).
  4. Resample every camera onto it. Return the `SyncResult` and the list of
     resampled `Keypoints2D`, each now carrying the shared rate.

---

## 5. Step 2b: working out where the cameras are

### `mocap_pipeline/stage2_reconstruct/calibrate.py`: calibration from the performer

Calibration means finding each camera's lens numbers (its "intrinsics") and its
position and orientation (its "extrinsics"). The usual way needs a printed
pattern filmed by every camera. This module avoids that by using the
performer's own landmarks as the pattern: the same shoulder seen by two cameras
at the same instant is a correspondence, and enough correspondences pin down
where the cameras are.

The method is the team's own. The lens numbers are kept fixed (iPhones give the
real focal length in the video metadata; other cameras use a field of view).
Only positions and orientations are solved for. The heavy numerical work is
done by two libraries: OpenCV for the geometry and aniposelib for the joint
refinement. The result has no real-world scale and uses camera 0's frame of
reference; the next module fixes both.

- **`CalibrationError`** (class). Raised when the performer did not move enough
  or a camera saw too little; the caller falls back to the board.
- **`rig_to_group(rig)`** and **`group_to_rig(cgroup, camera_ids, errors, is_metric)`**.
  Convert between our `CameraRig` and aniposelib's camera group, in both
  directions. The only difference is how rotations are stored: we keep a 3 by
  3 matrix, aniposelib keeps a 3-number rotation vector; OpenCV's Rodrigues
  function converts between the two.
- **`_stack(keypoints)`**. Pile every camera's points into one array of shape
  (cameras, frames, 33, 2) and likewise for confidence.
- **`_calibration_points(points, confidence)`**. Keep only the 12 calibration
  landmarks, and only where confidence is at least 0.8. Everything else
  becomes NaN.
- **`_n_distinct(pa, pb, size_a, size_b)`**. How many distinct positions two
  cameras saw together. Positions are rounded to a grid of 1 percent of the
  image width before counting, because a performer standing still produces
  the same few points over and over with jitter, and a raw count would
  overstate how much they moved.
- **`_move_origin_to(cgroup, origin)`**. Re-express every camera so the chosen
  camera sits at the origin looking down its own z axis: multiply each
  rotation by the origin camera's rotation transposed and adjust each
  translation to match.
- **`_per_camera_errors(cgroup, flat, camera_ids)`**. Triangulate all the
  calibration points with the group, project them back into each camera, and
  average the pixel distance from where they were detected. One number per
  camera: the calibration quality.
- **`initial_intrinsics(width, height, hfov_deg)`**. A first guess at the lens
  numbers from the image size and the horizontal field of view: the focal
  length in pixels is half the width divided by the tangent of half the field
  of view; the image centre is the principal point; no skew.
- **`select_correspondences(a, b)`**. Matching points seen by both cameras:
  the calibration landmarks confident in both, as two arrays whose row i is
  the same landmark at the same instant. Raises `CalibrationError` if fewer
  than 200 distinct positions were seen together.
- **`estimate_relative_pose(pts_a, pts_b, K_a, K_b)`**. The rotation and
  translation of camera b relative to camera a.
  1. Convert both point sets to "normalised" coordinates by undoing each lens,
     so cameras with different lenses can be compared.
  2. Estimate the essential matrix with RANSAC ("random sample consensus": try
     many small random subsets, keep the answer most points agree with). The
     pixel tolerance from the configuration is scaled into normalised units.
  3. Recover the rotation and translation from it, picking the one of the four
     mathematically possible answers that puts the landmarks in front of both
     cameras.
  The translation comes out with length 1: the scale is unknown at this stage
  by design.
- **`refine_intrinsics(...)`**. Not used. A placeholder for a published method
  that also adjusts the lens numbers; the team's calibration keeps them fixed.
- **`reprojection_error(pts_2d, pts_3d, K, R, t)`**. Project 3D points into a
  camera and measure the mean pixel distance to the detected 2D points.
- **`calibrate_pair(a, b, K_a_fixed, K_b_fixed)`**. Two-camera calibration:
  lens numbers from the given values or the first guess, correspondences,
  relative pose, then one refinement of both cameras together with
  aniposelib's bundle adjustment (adjusting the camera positions to minimise
  reprojection error over all points at once), with camera a moved to the
  origin.
- **`_place_camera(placed_group, flat_placed, flat_new, K_new, name)`**. Add
  one more camera to cameras already placed. Triangulate the 3D positions of
  the calibration landmarks from the placed cameras, keep the ones the new
  camera also saw, and solve the "perspective-n-point" problem: given 3D
  points and where they appear in an image, find the camera's position and
  orientation. Uses OpenCV's RANSAC version with an 8 pixel tolerance. Raises
  `CalibrationError` if fewer than 50 points are shared or the solve fails.
- **`calibrate_rig(keypoints, intrinsics)`**. The whole calibration for two or
  more cameras.
  1. Lens numbers: the given ones, or the first guess per camera.
  2. Prepare the calibration points for every camera.
  3. Count distinct shared positions for every pair of cameras and start from
     the best pair: relative pose, then refine the two together. Record the
     pair and the counts in the metrics.
  4. Add the remaining cameras one at a time, always the one that sees the
     most of the already-triangulated landmarks, with `_place_camera`.
  5. With three or more cameras, refine all of them together once more.
  6. Move camera 0 to the origin and compute each camera's error.
  Gives back the `CameraRig`, not yet in metres.
- **`add_camera(rig, existing, new, K_new)`**. Add one phone to an already
  calibrated rig without redoing everything: place it from the landmarks the
  existing cameras see, refine the whole rig once, re-centre on camera 0.

### `mocap_pipeline/stage2_reconstruct/iphone_camera.py`: real lens numbers from an iPhone file

An iPhone writes its lens's 35 mm equivalent focal length into the video's
metadata. That number gives an exact focal length in pixels, better than any
field-of-view guess. The metadata is read directly from the file's QuickTime
"atoms" (the nested boxes a `.MOV` file is built from), without any video
library.

- **`FOCAL_35MM_KEY`**, **`MODEL_KEY`**, **`LENS_KEY`**: the metadata key
  names Apple uses. **`FULL_FRAME_DIAGONAL_MM`**: 43.27, the diagonal of a
  35 mm film frame.
- **`IPhoneMetadataError`** (class). Raised for files without the metadata.
- **`_atoms(data, start, end)`**. Walk the atoms between two byte positions,
  yielding each atom's four-letter type and the byte range of its contents.
  Handles the two size encodings and "runs to the end of the file".
- **`_find(data, start, end, kind)`**. The byte range of the first atom of a
  given type in a range, or None.
- **`_read_moov(path)`**. Read only the `moov` atom, which holds all the
  metadata, by walking the top level of the file and skipping over the large
  video data without loading it.
- **`read_metadata(path)`**. Inside `moov`, find the `meta` atom, then its
  `keys` list (the names) and `ilst` list (the values). Pair them up, decoding
  text, whole numbers and floating-point values by their type code. Gives
  back a dictionary from key name to value, or an empty one if the file has
  no such metadata.
- **`intrinsics_from_focal(size, focal_35mm)`**. Lens numbers from the 35 mm
  equivalent: the focal length in pixels is the 35 mm value times the image
  diagonal in pixels divided by the film diagonal in millimetres. Using the
  diagonal makes it work for portrait and landscape alike.
- **`is_iphone_video(path)`**. True if the file carries the focal length key.
- **`iphone_intrinsics(path, size)`**. The lens numbers and the metadata for
  one video, raising if the focal length is missing.
- Run as a script, it prints the model, lens and focal length of each video
  given.

### `mocap_pipeline/stage2_reconstruct/board_calibration.py`: the printed-board fallback

Used only when calibration from the performer fails or is too inaccurate. A
ChArUco board is a chessboard with small square markers in the white squares,
so each corner can be identified even when part of the board is hidden.

- Constants: 7 by 5 squares, 30 mm squares, 22 mm markers. Printers rescale,
  so measure the printed squares and pass the real size.
- **`make_board(square_length, marker_length)`**. The board definition for the
  aniposelib library.
- **`save_board_image(path, dpi)`**. A printable image of the board at 300
  dots per inch so each square comes out the intended size.
- **`calibrate_from_board(videos, square_length, marker_length)`**. One board
  video per camera; aniposelib detects the board in every frame and
  calibrates the group, returning it with the overall reprojection error.
- Run as a script: `make-board` saves the image, `calibrate` calibrates from
  videos and saves the result.

---

## 6. Step 2b, second half: real-world size and the floor

### `mocap_pipeline/stage2_reconstruct/scale_floor.py`

The calibration gives a rig whose units mean nothing and whose axes are camera
0's. An animation file needs metres, a floor, and an up direction. The
performer's known height sets the scale; their feet find the floor.

World axes after this step: Y up, Z pointing from the performer towards camera
0 along the floor, X to camera 0's right. The origin is on the floor under the
middle of where the performer's feet were.

- **`_mid(points, *names)`**. The average position of the named landmarks in
  every frame.
- **`_body_axis(points)`**. For every frame: the vector from the heel centre
  to the ear centre, its length, its direction, and whether the performer is
  standing upright. Upright means the knee centre, hip centre and shoulder
  centre each sit within 5 percent of the heel-to-ear length from the
  heel-to-ear line.
- **`scale_factor_from_height(pose, performer_height_m)`**. Metres per rig
  unit.
  1. Find the upright frames. Fewer than 10 and it raises with a message
     asking the performer to stand still facing the cameras.
  2. The expected heel-to-ear distance is the stated height minus 12 cm for
     the skull above the ears minus 3 cm for the heel landmark above the
     floor.
  3. Divide that by the median measured heel-to-ear length over the upright
     frames.
- **`estimate_floor(pose)`**. The floor plane, on a pose already in metres.
  1. A rough up direction: the median heel-to-ear direction over the upright
     frames (or all frames if too few are upright).
  2. Gather every heel and foot-tip position over the whole take and keep the
     lowest 20 percent along that direction: feet on the ground.
  3. Fit a plane to those points by finding the direction they vary least in
     (a singular value decomposition of the centred points; the smallest
     singular vector is the plane's normal). Flip the normal to point towards
     the head.
  4. Trust the plane only if the feet covered an area rather than a line or a
     spot (the second singular value is more than three times the third) and
     the plane's normal is within 30 degrees of the body's up direction.
     Otherwise use the body's up direction as the normal. Record all of this
     in the metrics.
  5. The floor point is the centre of the low foot points, lowered by the
     3 cm heel offset.
- **`make_metric(rig, pose, performer_height_m, rescale)`**. Apply all of it
  to the rig.
  1. Scale every camera's translation by the scale factor (skipped when the
     rig came from the board, which is already in metres).
  2. Find the floor normal and point on the scaled pose.
  3. Build the new world axes: Y is the floor normal; Z points from the floor
     point towards camera 0, flattened onto the floor; X is their cross
     product.
  4. Rewrite every camera's rotation and translation in those axes with the
     floor point as the origin.
  5. Mark the rig as metric and return it.

---

## 7. Step 2c: from 2D to 3D

### `mocap_pipeline/stage2_reconstruct/triangulate.py`

Each camera gives a ray from its centre through a landmark's pixel.
Triangulation finds the 3D point closest to all those rays. The maths is the
direct linear transform in aniposelib, run on every landmark of every frame at
once.

- **`triangulate_point(...)`**. Not used; a placeholder for a per-point
  weighted version.
- **`triangulate_sequence(keypoints, rig)`**. Takes the synced landmarks and
  the rig. Gives back a `Pose3D`.
  1. Set any observation with confidence under 0.5 to NaN so it is ignored.
  2. Triangulate everything. A landmark seen by fewer than two cameras comes
     out NaN.
  3. Outlier removal, repeated up to "cameras minus two" times: project every
     3D point back into each camera that contributed; where the worst camera
     is more than 15 pixels off and at least three cameras contributed, drop
     that camera's observation for that point and triangulate the point again.
  4. Any point whose mean reprojection error is still over 15 pixels is set
     to NaN.
  5. Record the mean error overall and per landmark, the views dropped, the
     points that failed, and the count seen by fewer than two cameras.
  6. The number of contributing cameras per point goes into `num_views`, with
     failed points set to 0.

---

## 8. Step 2c, clean-up: filling gaps and smoothing

### `mocap_pipeline/stage2_reconstruct/smooth.py`

- **`_runs(mask)`**. The start and end of every unbroken run of true values in
  a one-dimensional true/false array. Used to work on each continuous stretch
  of data separately.
- **`fill_gaps(pose)`**. Per landmark and per axis, a run of missing frames
  no longer than 10 frames, with data on both sides, is filled by a straight
  line between the neighbours. Longer runs stay missing and are counted.
  Filled points keep a view count of 0 so they can be told from measured
  ones. Records the counts.
- **`SMOOTHERS`**: the two names, `savgol` and `butterworth`.
- **`_savgol(fps)`**. Builds the Savitzky-Golay filter: a quadratic is fitted
  by least squares through each window of 7 frames and the centre value is
  replaced by the fit. It keeps the shape of a fast peak such as a punch
  better than averaging. Returns the filter function, the shortest run it can
  filter (7 frames), and its settings for the metrics.
- **`_butterworth(fps)`**. Builds a zero-phase Butterworth low-pass filter:
  order 2 at 8 Hz, run forward and then backward over the data so the result
  has no lag. The cutoff must be below half the frame rate or it raises.
  Returns the filter function, the shortest run (one more than the filter's
  padding, 10 frames at these settings), and its settings.
- **`smooth(pose, method)`**. Choose the smoother (the configured default if
  none given; an unknown name raises), record the choice, then for every
  landmark filter each continuous run on its own, so holes do not spread,
  leaving runs shorter than the minimum untouched. Records how many were
  skipped.

---

## 9. Step 3: from points to a skeleton file

The three modules here are adapted from the open-source video2bvh project. The
changes for our data: Y up instead of Z up, medians instead of means, our
landmark names, and the maths vectorised over all frames at once.

### `mocap_pipeline/stage3_rig/skeleton.py`: a skeleton with fixed bone lengths

- **`REST_DIRECTIONS`**: for each skeleton joint, the direction of its bone
  from its parent in the rest pose, a T-pose: spine and head up, arms out
  sideways, legs down. **`END_SITE_DIRECTIONS`**: the stub added after each
  ankle and wrist (the foot pointing forward, the hand along the forearm),
  0.4 times the joint's own bone length.
- **`_fill_missing(positions)`**. Frames where a skeleton joint is missing are
  filled by a straight line from the nearest frames that have it, or copied
  from the nearest frame at the start or end. A joint never seen in the whole
  take raises an error, because no skeleton can be built.
- **`rig_joint_positions(pose)`**. Build the 17 skeleton joints from the 33
  landmarks using the sources table in `joints.py` (average or weighted sum),
  then fill missing frames. Returns an array with no NaN, shape (frames, 17, 3).
- **`bone_lengths(rig_positions)`**. For each joint with a parent, the median
  over all frames of its distance to the parent. Left and right versions of a
  bone are averaged so the skeleton is symmetric. Returns a dictionary from
  joint name to length in metres.
- **`rest_pose_offsets(lengths)`**. The T-pose the file declares: each joint's
  offset from its parent is its rest direction times its bone length. End
  sites after the ankles and wrists are added under the name
  `<joint>EndSite`.

### `mocap_pipeline/stage3_rig/rotations.py`: positions into joint rotations

An animation file stores, per frame, how each joint is rotated relative to its
parent, plus where the root is. Positions alone do not say how a limb is
twisted, so each joint's orientation is built from two directions measured in
the pose.

- **`FRAME_RULES`**: for each rotating joint, which measured direction is its
  primary axis and which is its secondary. For example the hips' x axis is
  the line from the right hip to the left hip and their y axis is the line up
  the spine.
- **`_normalize(v)`**. Vectors scaled to length 1, safely.
- **`_frame_from_axes(primary_axis, primary, secondary_axis, secondary, fallback)`**.
  Build a rotation matrix per frame whose chosen axis points exactly along the
  primary direction and whose second chosen axis points as close to the
  secondary direction as it can while staying perpendicular. The third axis
  follows from the right-hand rule. Where the two directions are nearly
  parallel, for instance an arm raised straight up, the fallback direction is
  used as the secondary instead.
- **`bone_rotation(rest_direction, current_direction)`**. The smallest rotation
  taking one unit vector onto another, by Rodrigues' formula: the axis is
  their cross product, the angle comes from their dot product. Handles the
  parallel and opposite cases.
- **`solve_rotations(rig_positions, rest_offsets)`**. The whole step.
  1. Measure the body's up (thorax to neck), left (right shoulder to left
     shoulder) and forward (their cross product) directions per frame.
  2. For every joint with a rule, build its world orientation from the rule's
     two directions, using the body forward or up direction as the fallback.
     Ankles and wrists, whose only child is an end site, copy their parent's.
  3. Each joint's local rotation is its parent's world orientation transposed
     times its own world orientation. The root's local rotation is its world
     orientation.
  Returns the root position per frame (the hip position) and the local
  rotation matrices, shape (frames, 16, 3, 3), for the rotating joints in
  skeleton order. The T-pose has every joint's orientation equal to the
  identity, which is why a measured orientation can be used directly.
- **`to_euler_degrees(local_rotations, order)`**. Convert the rotation
  matrices to three Euler angles each, in the channel order the file declares
  (Z, X, Y), using scipy's rotation class, then unwrap them over time so a
  joint does not jump by 360 degrees between frames.

### `mocap_pipeline/stage3_rig/bvh_writer.py`: writing the file

The format is BVH, Biovision Hierarchy, a plain text format with two parts: a
HIERARCHY section declaring the skeleton as nested joint blocks, each with its
offset from its parent and the channels it animates, and a MOTION section with
one line per frame holding every channel value in hierarchy order. Units are
centimetres by convention; the file is read as is by Blender and by the web
viewer's loader.

- **`CM_PER_M`**: 100. **`ROTATION_ORDER`**: `"ZXY"`.
- **`_children(name)`**. A joint's children, from the parents table.
- **`channel_order()`**. The rotating joints in the order the hierarchy writes
  them, depth first from the root. The motion lines must follow this order.
- **`write_hierarchy(lines, rest_offsets)`**. Append the hierarchy to a list
  of lines by recursion from the root: `ROOT` for the hip with six channels
  (position and rotation), `JOINT` for every other joint with three rotation
  channels, each with its offset in centimetres, and an `End Site` block after
  every leaf joint, using the stored end-site offset when there is one.
- **`write_bvh(path, rest_offsets, root_positions, euler_degrees, fps)`**.
  Write the hierarchy, then `MOTION`, the frame count, the frame time as one
  over the frame rate, then one line per frame: the root position in
  centimetres followed by each joint's three angles, reordered to match the
  hierarchy. Written as plain ASCII.

---

## 10. The conductor: `mocap_pipeline/run_pipeline.py`

The one file that knows the order of the steps. Everything else calls `run()`.

- Constants: the backend folder, the default output folder `backend/output/`,
  the default output and calibration paths, and `STAGES`, the names a run can
  stop after: keypoints, sync, calibrate, triangulate.
- **`default_model_path()`**. The pose model file: the `MODEL_FILEPATH`
  environment variable (loaded from a `.env` file if the dotenv package is
  installed), else the path in the configuration.
- **`camera_types(video_paths, choices)`**. iPhone or webcam per video: as
  stated, or detected from the metadata when the choice is "auto".
- **`camera_intrinsics(keypoints, video_paths, types, fovs)`**. Lens numbers
  per camera: from the metadata for iPhones, printing the model and focal
  length, falling back to the field of view if the metadata is missing; from
  the field of view for everything else.
- **`calibrate_cameras(keypoints, video_paths, types, fovs, max_error_px, charuco_videos)`**.
  Try calibration from the performer. If it raises, or its mean error is
  above the limit, fall back to the board: if no board videos were given,
  stop with a message saying which to record; otherwise calibrate from the
  board, re-centre on camera 0, and return that rig flagged as from the
  board.
- **`camera_ids_for(video_paths)`**. A stable id per video: the file name
  stem, prefixed with `camN_` when two videos share a stem, which happens
  when two phones both save `IMG_0001.MOV`. Decided before detection so a
  resumed run can find a camera's file without re-running it.
- **`_mtime(path)`**, **`_up_to_date(path, *inputs)`**. A file is up to date
  if it exists and is at least as new as every existing input file.
- **`_stop(stage, stop_after)`**. True, with a printed note, if the run should
  end after this stage.
- **`run(video_paths, out_path, ...)`**. The public entry point. Options:
  performer height, model path, camera types, fields of view, clap times,
  calibration path, recalibrate, the error limit, board videos, whether to
  smooth, whether to write the animation, resume, stop-after, detector,
  smoother. It validates the counts and names, opens a metrics run, calls
  `_run_stages` inside a total timer, and closes the run as done, stopped
  early, or failed with the error text. The metrics and log files are written
  even when the run fails.
- **`_run_stages(...)`**. The steps in order.
  1. Decide the camera ids, file paths and camera types.
  2. Step 1 per video. With resume, reuse the saved landmarks if the video's
     fingerprint still matches and the same detector made them; otherwise
     detect, timing it, and save with the fingerprint and detector name.
     Record the per-camera summary.
  3. Step 2a. With resume and a saved sync file for these cameras, take the
     clap times from it instead of searching the audio; resampling always
     runs because it is cheap. Save the sync file unless it was reused. Print
     and record the clap times and where they came from. A missing clap stops
     the run with a message explaining how to give the times by hand.
  4. Step 2b. Reuse an existing calibration file unless told to recalibrate,
     checking it has the right number of cameras. Otherwise require the
     height, calibrate, triangulate a rough pose with the new rig, convert to
     metres and find the floor (skipping the rescale for a board rig), and
     save. Record the errors and camera types.
  5. Step 2c. With resume, reuse the saved 3D points if the file is newer than
     the calibration, sync and landmark files; otherwise triangulate and
     save. Record the raw summary.
  6. Clean-up, unless disabled: fill gaps and smooth with the chosen
     smoother. Record the final summary. Write the viewer JSON.
  7. Step 3, unless disabled: write the animation file next to the JSON.
  After each of the first four steps it checks whether to stop early.
- **`export_bvh(pose, bvh_path)`**. Step 3 in four calls: skeleton positions,
  bone lengths and rest offsets, rotations, Euler angles, write. Records the
  bone length summary.
- **`per_camera(parser, name, values, n)`**. Command-line helper: a flag that
  takes one value for all cameras or one per camera.
- **`main()`**. Defines every command-line flag with its help text, checks the
  counts, and calls `run`.

---

## 11. The web API: `backend/api.py`

A small web server built with the FastAPI framework. The web frontend uploads
a take; the server runs the pipeline on it in the background, one take at a
time in a separate process; the frontend polls for status and downloads the
results. Each take lives in its own folder under `backend/output/`, named by
date, time and a short random suffix, with a `status.json` record, a
`log.txt`, the uploaded videos, and the pipeline's own files.

Importing this file must have no side effects, because the worker process is
started fresh and imports it again.

**Take records.**

- **`take_dir(take_id)`**, **`new_take_id()`**, **`now_iso()`**. The folder for
  a take, a new id, the current time as text.
- **`_retry_sharing(action, attempts, pause_s)`**. Run a file action, retrying
  for a few milliseconds on an operating-system error. On Windows, a file
  one process is replacing cannot be opened by another at that instant, so
  the API's reads and the worker's writes of the status file can collide.
- **`write_status(folder, record)`**. Write the status record atomically:
  write to a temporary file in the folder, then rename it over the real one.
- **`_load_json(path)`**, **`read_status(folder)`**, **`update_status(folder, **fields)`**.
  Read the record (None if missing or unreadable), or read, change some
  fields, and write back.
- **`get_take(take_id)`**. The folder and record, or a 404 response, also for
  ids that do not look like ours.

**The worker process.**

- **`LogWriter`** (class). Stands in for standard output inside the worker:
  every printed line goes to `log.txt`, and lines that start with known
  phrases ("Detecting joints in", "Clap at", "Saved calibration", "Saved ...
  frames of 3D joints") update the stage in the status record, so the
  frontend can show progress.
- **`run_take(folder, video_paths, height_m)`**. One take start to finish:
  mark it running, install the log writer, call the pipeline's `run` with
  recalibration forced, and mark the take done or failed with the error text.

**The job queue.** The process pool hands jobs to its worker ahead of time and
those cannot be cancelled, so queued takes wait in the API's own queue and a
dispatcher thread feeds the pool one at a time.

- **`new_executor()`**. A pool with one worker process, started with "spawn"
  rather than "fork", because forking a running web server and then loading
  the pose model can hang.
- **`mark_interrupted()`**. On start-up, any take left queued or running by a
  previous server is marked failed.
- **`dispatch(state)`**. The dispatcher thread's loop: take the next item,
  skip it if it was cancelled while waiting, submit it to the pool, and pass
  the result or error to its future. If the pool's worker died hard, make a
  new pool and retry.
- **`lifespan(app)`**. What happens when the server starts (make the output
  folder, mark interrupted takes, create the pool, the job map, the queue and
  the dispatcher thread) and stops (cancel waiting jobs, stop the dispatcher,
  kill a running worker).
- **`stop_workers(executor)`**. Terminate the worker processes, with a path
  for newer Python versions and one for older.
- **`submit(take_id, video_paths, height_m)`**. Put a take on the queue with a
  future the frontend can cancel. When it finishes, if the worker process
  itself died rather than the pipeline failing cleanly, mark the take failed.
- **`delete_take(take_id)`**. Returns "deleted", "running" or "not_found". A
  queued take is cancelled first; a running one cannot be deleted.

**The upload.** The multipart body is streamed straight into the take folder
rather than held in memory, and stops as soon as one video passes the size
limit.

- **`UploadError`** (class). An error with a status code and a message.
- **`TakeUpload`** (class). A streaming multipart parser. Its callbacks run as
  the body arrives: at each part's headers it checks the field name (videos
  must be `cam0`, `cam1`, ... with `.mov` or `.mp4` names; text fields are
  anything else; a name given twice is an error), opens a file for a video
  part, and collects text parts up to 1 kilobyte; at each data chunk it
  enforces the per-video size limit from the `MOCAP_MAX_UPLOAD_MB` environment
  variable (default 800); at each part's end it closes the file or stores
  the text.
- **`camera_number(field)`**. `cam12` to 12, so fields sort numerically.
- **`check_upload(upload)`**. Validate: at least two videos named `cam0`
  onward with no gaps; no unexpected fields; a height between 1.0 and 2.5
  metres; a name of at most 100 characters; a project id of letters, digits,
  dash and underscore. Returns the video paths in camera order, the height,
  the name and the project id.

**The endpoints.**

| Method and path | Function | What it does |
|---|---|---|
| POST `/takes` | `create_take` | accept the upload, validate, write the record, queue the take; replies with the record and status 202 |
| GET `/takes` | `list_takes` | every take newest first, optionally filtered by project id |
| GET `/takes/{id}` | `get_take_record` | one take's record |
| GET `/takes/{id}/out3d.json` | `get_out3d_json` | the 3D points, once the take is done (409 before) |
| GET `/takes/{id}/out3d.bvh` | `get_out3d_bvh` | the animation file, once done |
| GET `/takes/{id}/metrics.json` | `get_metrics` | the quality numbers, once done or failed |
| GET `/takes/{id}/keypoints.json` | `list_keypoints` | which cameras have saved 2D landmarks, with sizes, frame counts and clap times |
| GET `/takes/{id}/keypoints/{camera}.json` | `get_keypoints` | one camera's 2D landmarks per frame, for the per-camera view |
| DELETE `/takes/{id}` | `delete_one` | delete a take; 409 if running |
| POST `/takes/delete` | `delete_many` | delete several, returning each result |

Helpers for those: **`result_file`** serves a file from a finished take;
**`finished_take`** is `get_take` plus the done-or-failed check;
**`clap_times`** reads the sync file; **`keypoints_json`** converts one
camera's landmarks to the frontend's JSON shape (pixels, null where missing,
timestamps from the video start, plus the clap time to subtract);
**`camera_sort_key`** orders `cam2` before `cam10`; **`DeleteRequest`** is the
body shape for the bulk delete.

---

## 12. The camera placement tool: `mocap_pipeline/placement/`

A separate tool, not part of the main flow. Given where the performer will be,
it scores a camera layout and searches for a better one. The method is from a
2015 paper by Rahimian and Kearney on placing motion capture cameras when the
body hides markers.

### `placement/metric.py`: how good is a layout

The idea: for one target point, imagine a vertical wall through it, turned
through all 360 degrees. For each orientation, only cameras in front of the
wall can see the point. The point's error is the total angle over which no two
front-side cameras make a usable pair. 0 is perfect, 360 means the point can
never be reconstructed.

- **`camera_centre(camera)`**. Where a camera stands in the world: minus R
  transposed times t.
- **`camera_sees(camera, point)`**. True if the point is in front of the
  camera, projects inside the image (the image size is taken as twice the
  principal point), and is within the effective range of 6 metres.
- **`convergence_angle_deg(camera_a, camera_b, point)`**. The angle at the
  point between the rays to the two cameras.
- **`is_triangulable(camera_a, camera_b, point)`**. True if that angle is
  between 40 and 140 degrees. Nearly parallel rays give poor depth; nearly
  opposite cameras see opposite sides of the body.
- **`_floor_azimuth(direction)`**. A direction's compass angle on the floor
  plane.
- **`point_error(rig, point)`**. The algorithm above.
  1. Cameras that see the point. None: 360 plus a penalty of 360. One: 360.
  2. Each seeing camera's floor azimuth from the point. The set of front-side
     cameras changes only at each azimuth plus or minus 90 degrees, so those
     angles cut the circle into sections where the set is constant.
  3. For each section, take its middle orientation, find the front-side
     cameras, and if no pair among them is triangulable, add the section's
     width to the error.
- **`layout_cost(rig, target_points)`**. The sum of point errors over all
  target points.
- **`target_points_from_pose(pose, max_points, seed)`**. The points to score
  on: the finite landmark positions from a recording, randomly subsampled to
  at most 300 so the layout is scored on where the performer actually moved;
  or, without a recording, a grid over the capture volume at three heights.

### `placement/anneal.py`: searching for a better layout

Cameras stand on tripods inside a rectangle of floor around the capture area
and all aim at one point, about hip height. The search moves one camera at a
time and keeps the best layout it ever saw.

- **`Constraints`** (class, a frozen dataclass). Where phones may stand: x and
  z ranges, tripod height range, a minimum floor distance from the aim point
  so no phone is inside the capture area, the aim point, and the image size
  and field of view used to build each camera.
- **`_unit(v)`**. A vector scaled to length 1.
- **`intrinsics(constraints)`**. Lens numbers from the image size and field of
  view, the same formula as calibration's first guess.
- **`look_at(camera_id, position, aim, K)`**. A camera at a position looking
  at the aim point: forward is towards the aim, right is forward crossed with
  up, down follows; those three rows are R, and t is minus R times the
  position.
- **`rig_from_positions(positions, constraints)`**. A rig of look-at cameras,
  one per position.
- **`_random_position(constraints, rng)`**. A random allowed position, retrying
  until it is outside the minimum distance.
- **`_clip(p, constraints)`**. Clamp a position into the allowed ranges.
- **`random_layout(num_cameras, constraints, rng)`**. Every camera at a random
  allowed position.
- **`optimise_layout(num_cameras, constraints, target_points, iterations, seed, step_m, initial)`**.
  Simulated annealing.
  1. Start from a random layout or the given one; cost is the layout cost.
  2. Each step, move one random camera by a random Gaussian step of half a
     metre, clamped to the ranges; skip the move if it lands inside the
     minimum distance.
  3. Accept the move if the cost is lower. If higher, accept it anyway with
     probability exp(minus the increase divided by the temperature), where
     the temperature starts at 5 percent of the initial cost and falls to
     zero in a straight line over the iterations. This lets the search climb
     out of poor layouts early and settle late.
  4. Remember and return the best layout seen. The default of 2000 iterations
     is for trying ideas; the paper's 20000 is for a final answer.

---

## 13. The tests: `backend/tests/`

Not part of the pipeline, but the place to look when changing it. Each file
tests one area with small made-up data; none needs a real video or model.

- `conftest.py`: helpers that build small `Keypoints2D`, `SyncResult`,
  `CameraRig` and `Pose3D` objects, and two fake video files.
- `synthetic_scene.py`: a synthetic performer, cameras and routine with known
  truth, used to measure the whole of step 2 against the right answer.
- `test_synthetic_pipeline.py`, `test_metrics.py`, `evaluate_synthetic.py`:
  step 2 end to end on the synthetic scene; the last one is a script that
  prints a comparison table, including raw against each smoother.
- `test_resume.py`: the conductor's resume, stop-after, detector and smoother
  handling, with steps replaced by fakes that count calls.
- `test_smooth.py`: gap filling and both smoothers on a noisy sine wave.
- `test_io.py`: every save-and-load pair gives back what went in.
- `test_backends.py`: the detector interface and the 26-to-33 landmark mapping.
- `test_placement.py`: the placement metric and the annealer.
- `test_check_videos.py`: step 0 on small generated videos, made by
  `synthetic_video.py`.
- `test_api.py` and `test_api_upload.py`: the web API's queue, cancellation
  and restart recovery, and the streaming upload parser.
- `bvh_reader.py`: reads a BVH file back and recomputes joint positions, to
  check what step 3 wrote.

---

## Glossary

- **Landmark, joint, keypoint.** Three words for the same thing: one of the 33
  named body points the detector finds, such as LEFT_WRIST. "Joint" is also
  used for the 17 points of the skeleton in step 3.
- **Frame.** One still image from a video. Frame rate is frames per second.
- **Confidence.** The detector's 0-to-1 score for how sure it is about a
  landmark. Low confidence is kept in step 1 and filtered out later.
- **NaN.** "Not a number", the floating-point value used everywhere here to
  mean "missing". It propagates: any calculation with a NaN in it gives NaN,
  which is what we want.
- **Pixel coordinates.** x to the right and y down, from the top-left corner
  of the image.
- **Intrinsics, the lens numbers, K.** A 3 by 3 matrix holding the focal
  length in pixels (how strongly the lens magnifies) and the principal point
  (where the optical axis meets the image, normally the centre). It turns a
  direction in front of the camera into a pixel.
- **Extrinsics, R and t.** Where the camera is and which way it points, as a
  rotation matrix and a translation vector that move world points into the
  camera's own coordinates.
- **Calibration.** Finding the intrinsics and extrinsics.
- **Correspondence.** The same landmark seen in two cameras at the same
  instant. Calibration is built from many of these.
- **Essential matrix.** A 3 by 3 matrix that encodes the relative rotation and
  translation between two cameras, estimated from correspondences.
- **RANSAC.** Random sample consensus: a way to fit a model when some data
  points are wrong. Fit to a small random subset, count how many points agree,
  repeat many times, keep the fit most points agreed with.
- **Perspective-n-point, solvePnP.** Given some 3D points and where they appear
  in an image, find the camera's position and orientation.
- **Bundle adjustment.** Adjusting all camera positions at once to minimise the
  total reprojection error over every point.
- **Triangulation.** Finding a 3D point from where it appears in two or more
  cameras: the point closest to all the rays. The direct linear transform
  (DLT) is the standard linear way to solve it.
- **Reprojection error.** Take a 3D point, project it back into a camera with
  that camera's calibration, and measure the pixel distance from where the
  landmark was actually detected. The main quality number in steps 2b and 2c.
- **Singular value decomposition.** A matrix factorisation that, among other
  things, finds the directions in which a cloud of points varies most and
  least. The least-varying direction of a flat cloud is the normal of its
  plane.
- **Savitzky-Golay filter.** Smoothing by fitting a low-degree polynomial
  through each sliding window of points and taking the fitted centre value.
  From a 1964 paper on cleaning up chemistry instrument traces; it keeps the
  shape of peaks better than a plain moving average.
- **Butterworth filter.** A standard low-pass filter with a flat response below
  its cutoff frequency. Running it forward and then backward removes the delay
  it would otherwise introduce.
- **Euler angles.** Three rotation angles about three axes in a declared
  order, how the animation file stores a joint's rotation.
- **BVH.** Biovision Hierarchy, the plain-text skeleton animation format
  written in step 3 and read by Blender and the web viewer.
- **T-pose, rest pose.** The neutral pose the skeleton is declared in: arms out
  sideways, legs straight down.
- **Human3.6M skeleton.** A 17-joint skeleton layout from a research dataset,
  widely used in pose work; our step 3 uses it.
- **MediaPipe, RTMPose.** The two pose detectors available in step 1.
- **ChArUco board.** A chessboard with small coded markers in the white
  squares, used as a fallback calibration target.
- **QuickTime atoms.** The nested boxes an Apple `.MOV` file is made of; the
  lens metadata lives in one of them.
- **Dataclass.** A Python class that is only a container of named fields.
- **Context manager.** A Python object used with `with ...:` so that something
  is set up at the start of the block and cleaned up at the end.
- **numpy array.** The standard Python container for numeric grids; the shape
  such as (F, J, 3) lists its dimensions.
- **JSON.** A plain-text format for nested lists and dictionaries, readable by
  people and by every language.
- **FastAPI, uvicorn.** The web framework the API is written in and the server
  program that runs it.
- **Multipart upload.** The way a browser sends several files and fields in
  one request, as parts separated by a boundary string.
