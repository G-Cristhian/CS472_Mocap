# Field test protocol

How to record a motion capture session with phones so that `backend/mocap_pipeline` can process it. Written for whoever is holding the phones on the day. Read it once before the session and keep sections 5 and 9 open during it.

Everything here follows from how the pipeline works (`backend/mocap_pipeline/README.md`): every camera must hear one clap in its first 10 seconds[^1], the performer's own body calibrates the cameras during a short walk, their standing height sets the scale, and nothing may move a camera after the clap.

---
## 1. What this session is for

1. **Does the pipeline run on real footage at all.** Clap found, calibration under 10 px error[^2], a skeleton that stands upright and faces the right way in the viewer.
2. **How bad is fast motion.** The same punches, kicks and jumps at 60 fps and at 120 fps, so we can measure what frame rate buys us[^3] and whether the detector needs replacing.
3. **How many phones do we need.** Record every take with all phones; afterwards the pipeline is run again with only two or three of the videos, no extra recording needed.

Everything else (occlusion, turning away from the cameras, two performers) is a bonus. Fewer, complete takes beat many broken ones.

---
## 2. Kit

- At least 2 phones (there is no maximum; 3 or 4 is the sweet spot for one performer)[^4], fully charged, with at least 10 GB free each. Figure on about 100 MB per phone per minute at 1080p60, 400 MB at 4K60 or 1080p120.[^5]
- One tripod or firm stand per phone, chest height. A phone wedged on a chair will move when someone brushes past it. Tape to mark tripod feet on the floor.
- A tape measure (for the performer's height and the camera distances) and a roll of masking tape.
- Something that claps: hands are fine. A clapperboard or two blocks of wood are louder.
- A laptop with the repo set up (`cd backend && python -m pip install -r mocap_pipeline/requirements.txt`, or [windows-setup.md](windows-setup.md) on Windows), a cable for each phone type, and a notebook or this file's take log.
- A space at least 5 m by 5 m with a flat floor, even light and a plain background. A gym or an empty classroom works. Avoid windows behind the performer.

---
## 3. Phone settings

Set these before leaving home and do not touch them on the day. Every phone should record at the **same resolution and frame rate** within a take set.

**Default for the session: 1080p at 60 fps.**[^6] 60 fps halves the motion blur of 30 fps. 1080p is plenty: the pose detector works on a downscaled image[^7], so 4K only costs storage, transfer time and decoding time. The 120 fps take set (section 6) is the one exception.

### iPhone (15, 16, 17, Pro or not)

Settings app, then Camera:

| Setting | Value | Why |
|---|---|---|
| Record Video | 1080p HD at 60 fps | section 3 above |
| Record Video, Auto FPS (or Auto Low Light FPS) | Off | the frame rate must not change mid take |
| Record Video, Enhanced Stabilization (if shown) | Off | stabilisation crops and warps the image; the calibration assumes a fixed lens[^8] |
| Record Video, HDR Video | Off | plain 8-bit files decode everywhere |
| Record Video, Lock Camera (if shown) | On | stops the phone switching lenses during a take |
| Record Video, Lock White Balance (if shown) | On | consistent colour for the detector |
| Record Slo-mo | 1080p HD at 120 fps | only used in the 120 fps take set |
| Formats, Camera Capture | Most Compatible | H.264 files open on any laptop. High Efficiency (HEVC) also works but needs the right codecs on Windows |

In the Camera app on the day: **1x lens only**, never 0.5x or the telephoto. Action mode off (the running-figure icon). Press and hold on the performer's position until "AE/AF LOCK" appears, after framing and before the clap, so focus and exposure cannot drift. Airplane mode or Do Not Disturb so a call does not interrupt recording.

Original iPhone files carry the lens focal length in their metadata and the pipeline reads it[^9] (`stage2_reconstruct/iphone_camera.py`). This is why iPhones need no field of view number and why section 8 insists on original files.

iPhone 16 Pro and 17 Pro can also record 4K at 120 fps in the normal video mode. Not needed for this session; 1080p slo-mo gives the same frame rate at a quarter of the storage.

### Galaxy Fold

Menu names are from One UI 6 and may differ slightly on your model. Camera app, Video mode:

| Setting | Value |
|---|---|
| Resolution chip at the top | FHD 60 (or UHD 60 if FHD 60 is not offered) |
| Super Steady (hand icon) | Off |
| Camera settings, Advanced video options, HDR10+ videos | Off |
| Camera settings, Advanced video options, High efficiency videos | Off |
| Camera settings, Advanced video options, Auto FPS | Off |
| Camera settings, Tracking auto-focus | Off |
| For the 120 fps take set | More, Slow motion, FHD 120 |

Same rules as the iPhone: 1x lens, press and hold to lock focus and exposure, Do Not Disturb on. The Fold's rear cameras are the same whether it is open or closed; closed is steadier on a tripod.

**The Fold needs a field of view number.** Android videos do not carry usable lens metadata[^10], so the pipeline takes the horizontal field of view in degrees with `--fov`. Measure it once, with exactly the video settings above, because stabilisation and resolution change the crop:

1. Stand the phone facing a wall, lens at a measured distance D from the wall (2 m is fine).
2. Stick a tape measure horizontally on the wall at lens height. Start recording, note the tape readings at the left and right edges of the frame, stop.
3. Visible width W is the difference. Field of view in degrees is `2 * atan(W / (2 * D))`[^11], converted to degrees. For W = 3.0 m at D = 2 m that is 73.7 degrees.

Write the number in the take log. Expect roughly 70 to 78 degrees for a Fold main camera. If there is no time to measure, 75 is a better guess than the pipeline's default of 65.[^12]

---
## 4. Setting up the space

**Where the phones go.** All cameras in an arc in front of the performer, 2 to 4 m from the middle of the capture area, lens at chest height[^13], tilted so the whole body with a margin above the head and below the feet stays in frame everywhere the performer will move. Spread them out; cameras bunched together cannot triangulate depth.[^15]

| Phones | Angles from straight ahead |
|---|---|
| 2 | -35 and +35 degrees |
| 3 | -60, 0 and +60 degrees |
| 4 | -65, -20, +20 and +65 degrees |[^14]

No camera behind or directly beside the performer. Every camera must see the performer's front during the calibration walk.

**Camera 0 is special.** The pipeline treats the first video given as the reference: the world is laid out facing it.[^16] Make camera 0 the phone pointing most directly at the performer (the 0 or -20 degree position), make it an iPhone, and keep the same phone in that role for the whole session.

**Mark everything.** Tape around each tripod foot and a tape cross on the floor at the centre of the capture area. If a phone is bumped it can be put back, and the take log says which takes are affected.

**Light and background.** Bright, even light from the front or above; 60 fps needs twice the light of 30 fps. Nobody but the performer in any camera's view, including people walking past in the background: the detector tracks one person and will happily pick the wrong one[^17]. Plain walls beat mirrors, posters and other people's gym bags.

**The performer.** Fitted clothes that contrast with the floor and walls, no baggy trousers, skirts or long open jackets. Hair tied back so the ears are visible (they set the head position and the height).[^18] Shoes on, the same shoes for the whole session. Measure their height in those shoes against a wall with the tape measure, to the centimetre, and write it in the log. The pipeline needs it in metres.

---
## 5. The recording routine (every take)

Do the whole routine on every take, even when the cameras have not moved. It costs 20 seconds and means any take can be processed on its own.

1. **Check.** Every phone on its tripod, framed, focus and exposure locked, correct mode (video or slo-mo), battery and storage fine. The performer standing on the centre cross.
2. **Start all phones.** One person goes round and presses record on each. Say "rolling" when the last one is going. From here on nobody touches a phone or tripod until the take is over.
3. **Clap, within 5 seconds of "rolling".** One single sharp clap, standing in the middle of the arc so every phone hears it about equally. Silence for a second before and after: no talking, no music, no doors. The pipeline looks for the clap in the first 10 seconds of each video and it has to be far louder than anything around it[^19]. If the clap is missed, section 11 explains how to type the times in by hand, which is tedious.
4. **Height pose, 3 seconds.**[^20] Performer stands still on the cross, upright, arms relaxed at their sides, facing camera 0. This measures their height in the footage.
5. **Calibration walk, 10 to 15 seconds.** The performer walks a loop that covers the whole capture area, turns to face each camera in turn, raises both arms up and out, and does a couple of lunges or squats. Keep both feet visible to all cameras: the floor is found from the lowest foot positions[^22]. The calibration counts how many different places the joints were seen in by each pair of cameras and needs several hundred[^21], so moving through the space matters more than time.
6. **The take itself.** Whatever section 6 calls for. Call "action" so the audio marks where it starts.
7. **Hold still for a second, then stop all phones.** Fill in the take log before anyone moves a tripod.

If anything went wrong (phone bumped, someone walked through, clap drowned out) note it and record the take again. Do not try to salvage it later.

---
## 6. Take plan

Each take is 20 to 40 seconds after the routine. Record all phones on every take. Order is by priority; stop when the time runs out.

| Set | Mode | Takes | Content | What it answers |
|---|---|---|---|---|
| A, baseline | 1080p60 | 2 |[^23] walk a square, squat, wave both arms, sit and stand | does the pipeline run end to end |
| B, fast | 1080p60 | 3 to 4 | jab-cross combinations, front kicks, jumping jacks, sprint on the spot, a sword or bat swing with a stick | how fast motion degrades the result |
| C, fast at 120 | 1080p120 slo-mo on every phone | same content as B | the frame rate comparison. Settings change on every phone between B and C: double check |
| D, turning | 1080p60 | 1 to 2 | slow spin on the spot, walk away from camera 0 and back | where the front-arc assumption breaks |
| E, second performer | 1080p60 | 1 to 2 | set A content with another person of a different height | does the scale step work for other bodies |

Keep the content of B and C identical, including order and count, so the two sets compare. Camera subsets (two or three phones) are tested afterwards from these same recordings.

---
## 7. Take log

One row per take, filled in before anyone touches a tripod. Copy this table into a notes app or print it.

| Take | Set | Time | Performer | Height (m, in shoes) | cam0 phone | cam1 phone | cam2 phone | cam3 phone | Mode and fps | Fold `--fov` | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | A | | | | | | | | 1080p60 | | |

Once per session also note: the distance and angle of each tripod from the centre cross, the room, the light. In Notes write anything that might matter later: a phone was bumped and reset, someone walked through, the clap was quiet, a tripod leg slipped.

---
## 8. Getting the files off the phones

**Only original files work.** Anything re-encoded loses the iPhone lens metadata and may change the frame rate, and a re-exported slo-mo clip is baked to 30 fps with a slowed section[^24]. Do not send videos through Messages, WhatsApp, Discord, Instagram, Google Drive's share sheet or any editing app.

- **iPhone to Mac.** Settings, Photos, Transfer to Mac or PC, set to **Keep Originals** first. Then AirDrop, or a cable with Image Capture or the Finder. iCloud Photos on the web works if you choose Unmodified Original when downloading.
- **iPhone to Windows.** Cable, open the phone in Explorer, copy from DCIM. Keep Originals applies here too.
- **Galaxy Fold.** Cable in file transfer mode, copy from DCIM/Camera. Smart Switch also keeps originals.

**Name and sort as you copy.** One folder per take, camera number first so the pipeline command is obvious:

```
field_test_2026-10/
  take01/
    take01_cam0_iphone16pro.MOV
    take01_cam1_iphone15.MOV
    take01_cam2_fold.mp4
  take02/
    ...
```

Camera numbers follow the arc from left to right as seen from the performer, with camera 0 as defined in section 4. Keep the same numbering for every take.

**Two copies before anything is deleted from a phone.** The laptop and an external drive or a cloud folder with original quality. Do not delete from the phones until the pipeline has run on the copies.

---
## 9. Check the files before you leave

Run this on the laptop at the venue, on every take, while the tripods are still up:

```
cd backend
python -m mocap_pipeline.check_videos ../field_test_2026-10/take01/*
```

On Windows, in PowerShell ([windows-setup.md](windows-setup.md)):

```
cd $HOME\CS472_Mocap\backend
$videos = (Get-ChildItem ..\field_test_2026-10\take01\* -Include *.MOV, *.mp4 | Sort-Object Name).FullName
.venv\Scripts\python.exe -m mocap_pipeline.check_videos $videos
```

For each video it prints the resolution, frame rate, length, whether the iPhone lens metadata is there, and the time it finds the clap (a video with no audio track fails that line). Then it cross-checks the claps between cameras. Anything it flags with WARNING or FAIL is a reason to record that take again now, while that is still cheap:

- no audio or no clap found: the phone was muted or the clap was too quiet;
- frame rate not what was set, or different between phones in a take[^25]: a setting was missed;
- ".MOV without iPhone lens metadata" on an iPhone video: the file was re-exported, copy it again;
- clap later than 10 seconds: it will not be found; retake or note the times by hand.

The full pipeline takes minutes per take and does not need to run at the venue.

---
## 10. Processing afterwards

The current version of this section, with the metrics file the pipeline now writes, is [processing-a-take.md](processing-a-take.md). The commands below still work.

One command per take, from `backend/`. iPhones ignore `--fov`; it applies to the Fold only. Give the performer's height from the log. Keep each take's output and calibration in its own folder.

```
python -m mocap_pipeline.run_pipeline \
    ../field_test_2026-10/take01/take01_cam0_iphone16pro.MOV \
    ../field_test_2026-10/take01/take01_cam1_iphone15.MOV \
    ../field_test_2026-10/take01/take01_cam2_fold.mp4 \
    --fov 75 --height-m 1.78 \
    --out output/take01/out3d.json --calibration output/take01/calibration.json
```

On Windows, the same command on one line, with `.venv\Scripts\python.exe` in place of `python` ([windows-setup.md](windows-setup.md)):

```
.venv\Scripts\python.exe -m mocap_pipeline.run_pipeline ..\field_test_2026-10\take01\take01_cam0_iphone16pro.MOV ..\field_test_2026-10\take01\take01_cam1_iphone15.MOV ..\field_test_2026-10\take01\take01_cam2_fold.mp4 --fov 75 --height-m 1.78 --out output\take01\out3d.json --calibration output\take01\calibration.json
```

What to write down from the console for each take: the clap time per camera, the calibration error per camera in pixels (under 10 is accepted, under 5 is good)[^26], and whether it finished. Then open `output/take01/out3d.bvh` in the frontend viewer (`cd frontend && npm install && npm run dev`, or on Windows [windows-setup.md](windows-setup.md) step 5; the Django backend must be running, [mac-setup.md](mac-setup.md) step 5; log in, open a motion, "Open .bvh / .json" bottom right of the viewport) or in Blender (File, Import, Motion Capture). The skeleton should stand on the floor, face the viewer, and look like the take.

**Rerunning.** The pipeline saves every stage next to `--out`. Add `--resume` to any rerun and MediaPipe is skipped; see "Rerunning and debugging" in the pipeline README. Tuning smoothing or recalibrating takes seconds instead of minutes.

**Camera subsets (set E of question 3).** Run the same take again with fewer videos and a different calibration file. Camera 0 must stay in the list:

```
python -m mocap_pipeline.run_pipeline take01_cam0_iphone16pro.MOV take01_cam1_iphone15.MOV \
    --height-m 1.78 --out output/take01_2cams/out3d.json --calibration output/take01_2cams/calibration.json
```

On Windows, again on one line:

```
.venv\Scripts\python.exe -m mocap_pipeline.run_pipeline take01_cam0_iphone16pro.MOV take01_cam1_iphone15.MOV --height-m 1.78 --out output\take01_2cams\out3d.json --calibration output\take01_2cams\calibration.json
```

**The 60 versus 120 comparison.** Process a set B take and its set C twin, open both BVH files, and look at the fast moments: the wrist on a punch, the foot on a kick. Jitter, a joint that lags behind, or gaps (null joints in the JSON) are what the frame rate change is supposed to reduce. Note that the pipeline currently resamples everything to 30 fps (`config.TARGET_FPS`)[^27]; the sharper frames still help, and raising the target to 60 is a one-line change planned once the footage is in.

---
## 11. When it goes wrong

Messages the pipeline prints, and what they mean on the day of recording.

| Message | Cause | Fix |
|---|---|---|
| `no clear clap in the first 10 s. The sharpest sound is at 2.31 s: 2.9x the background (need 4.0) ...` | clap too quiet for the room, or music or talking at that moment | if the time it names is the clap, rerun with `--clap-threshold 0.5` (also works with `check_videos`); if not, scrub each video in a player (QuickTime shows the time) and pass `--sync 1.25 0.80 1.10`, one time per video in order |
| `has no audio track` | phone muted or recorded without sound | `--sync` as above, or retake |
| `only N distinct joints seen by cam0 and cam1 together, need 200` | the calibration walk was too short or did not cover the space, or one camera could not see the performer | retake with a longer walk; or record the ChArUco board with every camera and use `--charuco-videos` (pipeline README) |
| `only N frames with the performer standing upright` | height pose too short or not facing the cameras | hold the pose for 3 full seconds |
| `feet seen in too few frames to find the floor` | feet cut off at the bottom of the frame | tilt the cameras down or move them back |
| `error X px is above --max-error` | a phone moved, the lens switched, a wrong `--fov` | check the take log for bumps; measure the Fold's field of view; `--recalibrate` |
| `has no focal length metadata (is it straight from an iPhone, not re-exported?)` (printed only with `--camera iphone`; with the default `--camera auto` such a file is silently treated as a webcam, visible only in the `Cameras:` line) | the file was re-encoded on the way off the phone | copy the original again (section 8); or run with `--camera webcam --fov 70` for that video as a stopgap |
| `calibration.json has 3 cameras but 2 videos were given` | reusing a calibration from a different camera set | `--recalibrate`, or a separate `--calibration` path per camera set |
| the skeleton tracks the wrong person or jumps between people | a bystander was in frame | nothing to fix afterwards; keep the view clear |

---
## 12. What this prototype cannot do yet

So that nobody tests for it by accident:

- One performer at a time. A second person in view breaks detection.
- Cameras must not move during a take. Hand-held phones will not calibrate.
- Every camera in front of the performer. Turning away from the arc loses the joints facing away (set D measures how badly).
- No fingers or facial expression in the output skeleton; hands end at the wrist.
- Output is 30 fps for now, and processing is offline, minutes per take. There is no live view.
- The Fold is calibrated from a field of view guess rather than lens metadata, so expect its camera to carry the largest error.

---
## Sources

Where each choice above comes from: a constant in the pipeline, a row on the design decisions sheet, a paper, or team judgement with no source yet.

[^1]: `CLAP_SEARCH_WINDOW_S = 10.0` in `backend/mocap_pipeline/config.py`; the clap method is D-008 on `docs/decisions/DECISIONS.md`.
[^2]: `CALIB_MAX_ERROR_PX = 10.0` in `backend/mocap_pipeline/config.py`, a starting guess (D-015). The synthetic benchmark gives 0.1 to 3 px, so 10 is loose by design.
[^3]: Open question: the pipeline resamples every camera to 30 fps (`TARGET_FPS`, D-009, issue #15), so this take set measures whether sharper frames help before the target is raised.
[^4]: `MIN_CAMERAS = 2` in `backend/mocap_pipeline/config.py`; two views are the minimum for triangulation (Hartley & Zisserman, *Multiple View Geometry in Computer Vision*, 2nd ed., Cambridge University Press, 2004, DOI 10.1017/CBO9780511811685, ch. 12; D-002). The former maximum of 4 was dropped on 2026-10-16 (D-001 rejected, D-024). "3 or 4 is the sweet spot" is team judgement: each joint needs any two cameras, and the synthetic benchmark shows 4 cameras lose fewer joints than 3 but are not more accurate per joint (`tests/evaluate_synthetic.py`).
[^5]: The per-minute sizes iOS shows under Settings, Camera, Record Video for each format (they vary with H.264 versus HEVC); rounded up for safety.
[^6]: Team judgement on frame rate: at auto exposure the shutter time roughly halves from 30 to 60 fps, so motion blur halves. No measurement yet; set C exists to make one.
[^7]: MediaPipe's pose model runs on a 256 x 256 crop: Bazarevsky et al., "BlazePose: On-device Real-time Body Pose tracking", arXiv:2006.10204, 2020 (unverified). RTMPose uses 256 x 192 in rtmlib's "balanced" mode, the default `mode` in `stage1_keypoints/backends.py`; the size itself is set inside rtmlib.
[^8]: The camera model is a pinhole with fixed intrinsics and no distortion (`schemas.Camera`, D-010). Stabilisation re-projects the image per frame, which that model cannot represent.
[^9]: `stage2_reconstruct/iphone_camera.py` reads `com.apple.quicktime.camera.focal_length.35mm_equivalent` from the QuickTime `moov` atom and turns it into the focal length in pixels.
[^10]: Team observation while writing `iphone_camera.py`: the Fold's MP4 carries no focal length key the pipeline can use. Not verified against Samsung documentation. Team judgement, no source. A candidate row for `docs/decisions/DECISIONS.md`.
[^11]: Pinhole geometry: the horizontal field of view of a lens that sees width W at distance D (Hartley & Zisserman, *Multiple View Geometry in Computer Vision*, 2nd ed., Cambridge University Press, 2004, DOI 10.1017/CBO9780511811685, ch. 6).
[^12]: 70 to 78 degrees is an estimate from phone main-camera specifications, not a measurement. The default 65 is `DEFAULT_HFOV_DEG` in `backend/mocap_pipeline/config.py`. `tests/test_synthetic_pipeline.py::test_wrong_field_of_view_costs_accuracy_but_still_runs` shows what a 10 degree error costs.
[^13]: 2 to 4 m: team judgement, chosen so the whole body fits a 1080p frame with margin. The placement paper the tool is built on used 3.65 m for marker cameras; the pipeline's own guess is `CAMERA_EFFECTIVE_RANGE_M = 6.0` in `backend/mocap_pipeline/config.py` (D-019).
[^14]: Superseded on 2026-10-16 by the rule in the pipeline README: any number from 2 up, spread evenly across an arc of up to about 130 degrees (D-024). These rows remain valid examples of it.
[^15]: `tests/test_synthetic_pipeline.py::test_narrow_baseline_is_much_worse_than_the_protocol_arc`: cameras 10 degrees apart give over 3x the error of cameras 70 degrees apart. The placement tool's usable convergence range is `MIN_CONVERGENCE_DEG = 40` to `MAX_CONVERGENCE_DEG = 140` in `backend/mocap_pipeline/config.py`, from Rahimian & Kearney 2015, DOI 10.1145/2821592.2821596 (D-019).
[^16]: `schemas.py` ("Camera 0 (the first video given) is the reference camera"), `calibrate._move_origin_to`, and `scale_floor.make_metric`, which points +Z from the performer toward camera 0 (D-013).
[^17]: MediaPipe runs with `num_poses=1`; RTMPose takes the largest detected person (`stage1_keypoints/backends.py`, D-007). Neither identifies who the performer is.
[^18]: Height is measured heel to ear in upright frames with fixed offsets for the skull top and the heel (`scale_floor.scale_factor_from_height`, `HEAD_TOP_ABOVE_EARS_M`, `HEEL_ABOVE_FLOOR_M` in `backend/mocap_pipeline/config.py`; D-012). The rig's Neck and Head also come from the ears (`joints.RIG_JOINT_SOURCES`).
[^19]: `CLAP_MIN_PROMINENCE = 4.0` (times the median loudness) and `CLAP_MIN_RISE = 2.0` (times the loudness 30 to 100 ms before) in `backend/mocap_pipeline/config.py`; the rise must complete within `CLAP_MAX_RISE_S = 0.025`.
[^20]: `MIN_UPRIGHT_FRAMES = 10` in `backend/mocap_pipeline/config.py` is a third of a second at 30 fps; 3 seconds is a margin for the performer settling and for frames the detector drops. The margin is team judgement.
[^21]: `CALIB_MIN_CORRESPONDENCES = 200` distinct joint positions per camera pair, on a 1% grid of the image (`calibrate._n_distinct`), in `backend/mocap_pipeline/config.py`.
[^22]: `scale_floor.estimate_floor` fits a plane to the lowest `FLOOR_LOWEST_FRACTION = 0.2` of heel and toe positions (`backend/mocap_pipeline/config.py`, D-013).
[^23]: The take plan is team judgement built around the three questions in section 1. Team judgement, no source. A candidate row for `docs/decisions/DECISIONS.md`.
[^24]: Team observation of iOS slo-mo exports; the original file keeps 120 fps and the pipeline reads the real frame times (`stage1_keypoints/detect.py`). Not verified against Apple documentation.
[^25]: `check_videos.py` warns under `MIN_RECOMMENDED_FPS = 50`; the pipeline itself accepts any rate and resamples (`stage2_reconstruct/sync.py`).
[^26]: Accepted: `CALIB_MAX_ERROR_PX = 10.0` in `backend/mocap_pipeline/config.py`. Good: the synthetic benchmark with realistic noise (1.5 px, 2% dropout, 0.5% outliers) gives about 1 to 3 px, so under 5 on real footage means the cameras and the lens model are close to right.
[^27]: `TARGET_FPS = 30.0` in `backend/mocap_pipeline/config.py`; D-009 on `docs/decisions/DECISIONS.md`, issue #15.
