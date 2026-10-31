# The design decisions, explained for a reviewer

Companion to `docs/decisions/DECISIONS.md` (76 rows, D-001 to D-076). Written 2026-10-30 against `main` at commit 1209a02 (merge of PR #110, "rtmpose-options"). Every code fact below was checked in that commit unless marked "not checked". Citations (DOIs, standards) were not opened; where the sheet's reviewer notes or the code's own comments bear on a citation, that is said. Tags: [VERIFIED] checked this session in the repo, [INFERRED] reasoned from what was checked, [STATED] taken from the sheet or a document without checking.

## Orientation

1. Rows per group: (1) filming 6, (2) accepts and refuses 7, (3) how the result is computed 22, (4) what the result looks like and its quality 7, (5) desktop tester 4, (6) web app and the two servers 22, (7) camera placement tool 5, (8) project process 3. Total 76; every row is in exactly one group.
2. Superseded rows (they carry a `to` link): D-001 (to D-024, no maximum camera count), D-047 (to D-048, the parallel-detection default), D-054 (to D-060, the Upload screen spec). They keep their own status as the record of the verdict they got [VERIFIED, DECISIONS.md Lineage column].
3. Two things merged on 2026-10-28 have no row yet: the chirp as an alternative sync signal (PR #107, `backend/mocap_pipeline/stage2_reconstruct/chirp.py`, `config.py:71-93`) and the RTMPose mode, device and tracking options (PR #110, `config.py:24-38`). They bear on D-008, D-022, D-023, D-045 and D-046 below [VERIFIED: `grep -i chirp docs/decisions/DECISIONS.md` finds nothing].
4. Group 1, filming, matters most through D-008 (the clap is the only clock), D-025 (how many phones and where, which replaces the old 2/3/4 table) and D-035 (the 3 second height pose that sets the scale); get those wrong and the take cannot be processed.
5. Group 2 matters most through D-002 (two cameras minimum, which cannot change), D-045 (how loud a clap must be, the one threshold a real take has already failed) and D-040 (the 1.0 to 2.5 m height check, now copied in four places).
6. Group 3 matters most through D-010 (our own calibration method, undocumented deviation from the paper), D-012 (height to metres, with two guessed anatomical offsets) and D-009 (everything resampled to 30 fps, which throws away the 60 and 120 fps the protocol asks for).
7. Group 4 matters most through D-030 (the metrics file every tool reads), D-031 (the pass/fail cut-offs, hard-coded in three places) and D-032 (the 2D keypoints contract the per-camera view would depend on).
8. Group 5 matters most through D-050 (colours a user reads as verdicts, borrowed from calibration), D-057 (Cancel really stops the workers) and D-041 (the progress bar's guessed weights).
9. Group 6 matters most through D-073 (the Django backend caps a motion at 4 cameras, bringing back the rejected D-001), D-075 (one render at a time across all users, and Android field of view never passed through) and D-056 (the Supabase buckets are public with no sign-in, even though no page routes to them any more).
10. Group 7 matters most through D-019 (the metric the tool optimises), D-029 (the room the tool assumes, 8 m square) and D-026 (the penalty without which the tool parks every camera in one spot); group 8 through D-058 (the test routine nothing enforces), D-068 (the design spec as single source of truth) and D-059 (the Windows setup rules).

The planned direction for the desktop tester (always produce a BVH, with every fallback recorded in the metrics; drop the ChArUco board entirely; never guess a clap, so a clap or a chirp is always required) is noted on each row it touches: D-003, D-008, D-011, D-012, D-013, D-015, D-016, D-035, D-045, D-046.

---

## Group 1: How you film (phones, room, clap, performer rules)

### D-008 · Every camera is put on one clock by finding a hand clap in its audio, then cross-checked against camera 0
**What it means for a user:** One sharp clap within the first 10 seconds of every recording is mandatory; without it the take fails at sync, and the filming procedure tells you to clap within 5 seconds of "rolling" with silence around it [VERIFIED, `docs/procedures/filming.md:106`]. Camera 0 (the first video you give) is the reference the others are checked against, so which phone is "cam0" matters.
**What it affects in the code:** `backend/mocap_pipeline/stage2_reconstruct/sync.py:96-151` finds the clap as the sharpest loud transient, `sync.py:168-197` cross-correlates each camera against camera 0 and warns instead of applying a shift over `CLAP_MAX_REFINE_S = 0.05` s (`config.py:62-67`). The row's "Where" (`sync.py:69`, `sync.py:142`) has drifted: the functions are now at lines 96 and 168 because a chirp alternative was added (`sync.py:210-232`, `chirp.py`) [VERIFIED].
**If it were reversed:** Without an audio sync the cameras would need a shared trigger or a visual flash, which phones do not offer, or manual times typed per video (`--sync`), which filming.md calls tedious [VERIFIED, `filming.md:106, 240`].
**What you are being asked to confirm:** That Shrestha, Barbieri and Weda 2007 really describes clap or onset based synchronisation of consumer cameras (the sheet says the DOI was not found); citation not checked. Also whether the new chirp signal should get its own row `from D-008`.
**Related rows:** D-045 and D-046 set the thresholds this method uses; D-013 points the floor's Z axis at the same camera 0; D-072 makes "slot 0" the reference in the Django model. Planned direction: a clap or a chirp becomes always required and never guessed, which keeps this row and makes the `--sync` hand-typed path the only escape.

### D-025 · Any number of phones from 2 up, spread evenly across a front arc of up to about 130 degrees, with "3 or 4 the sweet spot"
**What it means for a user:** You can bring two phones or six; you place them in an arc in front of the performer so the two outermost are 70 to 130 degrees apart, and the docs tell you more phones means fewer lost joints, not more accuracy per joint [VERIFIED, `backend/mocap_pipeline/README.md:134`, `docs/procedures/filming.md:19`].
**What it affects in the code:** Nothing in code enforces the arc; it is guidance in the README and filming.md. The row's "Where" `README.md:106` is now `README.md:134` [VERIFIED].
**If it were reversed:** Returning to a fixed 2/3/4 angle table (the old D-001 world) would make the docs simpler but would contradict D-024's "no maximum", and the arc rule costs nothing in code.
**What you are being asked to confirm:** The cited convergence-angle range (Rahimian and Kearney 2015, 40 to 140 degrees, also `config.py:161-162`) and the depth-from-baseline argument (Hartley and Zisserman) support the shape of the rule but not the 130 degree figure, as the sheet itself says; citation not checked. The "sweet spot" is team judgement from the synthetic benchmark [STATED, filming.md footnote 4].
**Related rows:** `from` nothing, but requested by D-024's reviewer notes; D-034 (distance and height) is the other half of placement guidance; D-029 and D-019 use different numbers in the placement tool; D-073 contradicts it by capping at 4.

### D-034 · Cameras stand 2 to 4 m from the middle of the capture area, lens at chest height, whole body in frame with margin
**What it means for a user:** When setting up tripods you keep each phone roughly 2 to 4 metres away, at chest height, tilted so the whole body with headroom and footroom stays in frame everywhere the performer moves [VERIFIED, `docs/procedures/filming.md:81`].
**What it affects in the code:** Nothing; it is a procedure. The pipeline's own distance assumption is `CAMERA_EFFECTIVE_RANGE_M = 6.0` in the placement tool (`config.py:165`), and the placement defaults put lenses at 0.8 to 1.8 m (`placement/anneal.py:28`), so three documents carry three different numbers [VERIFIED].
**If it were reversed:** Closer phones give bigger people in frame but risk cutting limbs off; farther ones lose pixel detail per joint. Changing the text costs nothing; the real cost is the mismatch with the tool's numbers.
**What you are being asked to confirm:** Needs human research: a measurement of detection confidence against distance on the actual phones would settle it, or a decision that the three numbers be reconciled.
**Related rows:** D-025 (arc), D-029 (placement defaults), D-019 (effective range).

### D-035 · The performer holds a "height pose" for 3 seconds, while the pipeline needs only 10 upright frames
**What it means for a user:** After the clap the performer stands still and upright on the centre mark, arms at the sides, facing camera 0, for a slow count of three; this is what lets the pipeline turn its arbitrary units into metres [VERIFIED, `docs/procedures/filming.md:107`].
**What it affects in the code:** `scale_floor.py:64-67` refuses the take with "only N frames with the performer standing upright" when fewer than `MIN_UPRIGHT_FRAMES = 10` (`config.py:127`; the row's `config.py:82` has moved) [VERIFIED]. D-031 then asks for 30 or more frames as the quality bar.
**If it were reversed:** A shorter pose would save a second per take but push more takes under 10 frames and fail them; dropping the pose entirely would need another scale source (a known object, a measured camera baseline).
**What you are being asked to confirm:** Needs human research: on real takes, how many upright frames a 3 second pose actually yields at 30 fps after detector dropouts; that decides whether 3 s is a margin or a bare minimum. Planned direction: if a take with too few upright frames must still produce a BVH, this error becomes a recorded fallback (unscaled or default-height output) rather than a stop.
**Related rows:** D-012 (how the height is used), D-031 (30 frame quality bar), D-040 (height range).

### D-036 · The field session is planned as five take sets (A baseline, B fast, C the same at 120 fps slo-mo, D turning, E a second performer), 20 to 40 s each, every phone on every take
**What it means for a user:** The session has a fixed shooting order and stop-when-time-runs-out rule, and camera subsets are tested afterwards from the same recordings rather than by re-shooting [VERIFIED, `docs/procedures/filming.md:117-123`].
**What it affects in the code:** Nothing; it is a plan on paper. "Where" still matches [VERIFIED].
**If it were reversed:** A looser plan risks coming home without the fast or occluded takes that D-039's detector comparison needs; a stricter one costs session time.
**What you are being asked to confirm:** Needs human research or an `out of scope` verdict: it is a procedure, not a code choice, and the sheet's own note says so.
**Related rows:** D-039 (needs calm, fast and occluded takes), D-009 (set C exists to test the frame rate question).

### D-037 · Non-iPhone cameras take their horizontal field of view from `--fov` (default 65 degrees); the Galaxy Fold is taken as 75 when not measured
**What it means for a user:** For an Android phone you must measure or guess a field of view number and write it in the take log, because its video file carries no lens information; iPhones need nothing [VERIFIED, `docs/procedures/filming.md:70-76`]. A wrong number shows up as the largest calibration error on that camera (`filming.md:260`).
**What it affects in the code:** `config.py:107` holds `DEFAULT_HFOV_DEG = 65.0` (the row's `config.py:62` has moved); `calibrate.py:112` seeds the focal length from it; `check_videos.py:100` warns that such a file needs `--fov` [VERIFIED]. The Django backend stores a `field_of_view_deg` per recording but never passes it to the pipeline (D-075), so there Android cameras always get 65 [STATED, D-075 notes; `rendering.py:59-74` passes no fov, VERIFIED].
**If it were reversed:** Refining the focal length during calibration (Liu et al.'s intrinsic refinement, left unimplemented at `calibrate.py:169-171`) would remove the need for the number at the cost of a less stable calibration.
**What you are being asked to confirm:** Needs human research: a measured field of view for the Fold at the exact video settings, against Samsung's documentation.
**Related rows:** D-010 (lens fixed during calibration, iPhone metadata), D-075 (the Django path drops the value), D-029 (placement tool uses the same default).

---

## Group 2: What the pipeline accepts and refuses (limits, thresholds, file rules)

### D-001 · At most 4 cameras per take (rejected)
**What it means for a user:** Nothing any more on the pipeline and FastAPI path: the cap was removed, and you may give as many videos as you like [VERIFIED, `config.py:18-22` says "no upper limit (design decision D-024)"; `api.py:71`].
**What it affects in the code:** No `MAX_CAMERAS` exists in `config.py`, `run_pipeline.py` or `api.py` [VERIFIED by grep]. The row's "Where" (`config.py:14`, `api.py:59`) now points at the minimum instead. But the cap has come back elsewhere: the Django backend's `MAX_CAMERAS = 4` (`backend/motionboxpro/apps/motions/serializers.py:12`), the slot validator `MaxValueValidator(3)` (`motions/models.py:172`) and the picker's `MAX = 4` (`frontend/src/features/motions/AddRecordingDialog.tsx:11`) [VERIFIED].
**If it were reversed:** Reinstating a cap would protect processing time (each camera adds detection time linearly, `config.py:21`) at the cost of the "spoken, not designed" objection in the reviewer note.
**What you are being asked to confirm:** Rejected on 2026-10-16; D-024 replaced it. The open question is that D-073 and D-060 re-introduce the 4 without lineage to this row.
**Related rows:** to D-024; contradicted by D-060 and D-073; D-002 keeps the minimum.

### D-002 · At least 2 cameras per take, and at least 2 cameras must see a joint for it to be placed in 3D
**What it means for a user:** Fewer than two videos are refused outright ("Give at least 2 videos, one per camera"), and any joint only one phone saw is left as a hole in the result [VERIFIED, `run_pipeline.py:393-395`, `api.py:456-457`, `triangulate.py:28-30`].
**What it affects in the code:** `config.py:22` (`MIN_CAMERAS = 2`; the row's `config.py:14` has moved) and `config.py:135` (`MIN_CAMERAS_PER_JOINT = 2`). Note that processing-a-take.md footnote 8 says `MIN_CAMERAS_PER_JOINT` is not read: the "2" is fixed in `triangulate.py:29-33` and `:77` [VERIFIED].
**If it were reversed:** A single camera cannot give depth, so the only "reversal" would be monocular 3D lifting, a different product.
**What you are being asked to confirm:** That Hartley and Zisserman 2004 chapter 12 (triangulation needs two views) is the right reference; citation not checked, but the claim is textbook geometry and the chapter number matches the standard edition [INFERRED].
**Related rows:** D-004 (how the two or more views are combined), D-024, D-054 and D-073 restate the 2-minimum.

### D-024 · No maximum camera count per take; the minimum of 2 stays
**What it means for a user:** You may process five or six phones; the trade is time, since every extra camera adds its own detection run [VERIFIED, `config.py:19-21`].
**What it affects in the code:** `config.py:22`, `run_pipeline.py:393`, `api.py:71` and `:456` accept any count from 2 with camera fields `cam0..camN` by pattern. The row's "Where" was marked "pending: issue to be opened"; the change was made in 6c3885a and the lines are now those above, so the "Where" is stale [VERIFIED].
**If it were reversed:** See D-001; a cap would need a reason such as memory (D-048 notes each detection process takes 1 to 2 GB).
**What you are being asked to confirm:** Needs human research: whether an upper bound is needed for processing time or memory, with a measurement of a 6 camera take. The arc guidance it asked for exists as D-025.
**Related rows:** from D-001; D-025 (arc rule); D-048 (per-process memory is the practical limit); D-060 and D-073 ignore it.

### D-038 · Only original phone files are accepted; re-encoded or re-exported files lose lens metadata and may change the frame rate
**What it means for a user:** Copy videos off the phone by cable or AirDrop, never through a messaging app, a share sheet or an editor; a re-exported iPhone slo-mo clip becomes 30 fps with a slowed section and is useless [VERIFIED, `docs/procedures/filming.md:143`].
**What it affects in the code:** Only partly enforced: `check_videos.py:97` warns on a .MOV without iPhone lens metadata ("re-exported?") and `:89` warns below `MIN_RECOMMENDED_FPS = 50` (`check_videos.py:29`); the pipeline itself falls back to `--fov` for such a file (`run_pipeline.py:93`) [VERIFIED]. The Django upload accepts any file OpenCV can open (D-076).
**If it were reversed:** Accepting re-encoded files would be friendlier but would silently calibrate iPhones from the 65 degree default and mis-time slo-mo takes.
**What you are being asked to confirm:** Needs human research: Apple's documentation on what metadata an exported clip keeps, or a test export of one slo-mo clip through Photos and Messages compared in `check_videos`.
**Related rows:** D-037 (fov fallback), D-054 and D-076 (what the two uploaders accept), D-009 (frame rate).

### D-040 · The performer's height is accepted only between 1.0 and 2.5 m
**What it means for a user:** Typing a height outside that range is refused by the API ("height_m must be between 1.0 and 2.5 metres"), by the desktop tester ("Height must be between 1 and 2.5 metres") and by the Django model [VERIFIED, `api.py:76, 470-471`; `desktop/src/renderer/main.ts:145`; `desktop/src/renderer/index.html:33`; `backend/motionboxpro/apps/motions/models.py:124`].
**What it affects in the code:** The same two numbers now live in four places (API, desktop, Django `MotionVersion.height_m`, Django `Performer.height_m`, plus the unrouted `FootagePage.tsx:47`), so a change needs four or five edits. The row's "Where" lines have moved (`api.py:70` is now `:76`, `main.ts:104` is now `:145`, `index.html:27` is now `:33`) [VERIFIED].
**If it were reversed:** Widening the range costs nothing technically; the check only protects against typing centimetres by mistake. Narrowing it would wrongly refuse tall performers.
**What you are being asked to confirm:** Needs human research: whether these bounds should come from a population height table (the sheet's lead, NCD-RisC 2016, gives means only) or simply be declared a typo guard and approved as such.
**Related rows:** D-012 (the height sets the scale), D-054 and D-060 restate it, D-076 notes the four copies.

### D-045 · A clap must be at least 4 times the median loudness of its 10 s search window and 2 times louder than the moment 30 to 100 ms before it (lowered from 8 and 3)
**What it means for a user:** A quieter clap now passes than before 2026-10-19, because real takes were being refused as "not loud enough against the room"; the 25 ms rise-time test is what still rejects speech and music [VERIFIED, `config.py:51-61`].
**What it affects in the code:** `config.py:55` and `:58` (the row's `:32` and `:35` have moved); applied in `sync.py:112-113` and `:134` [VERIFIED]. The chirp signal has its own acceptance score `CHIRP_MIN_SCORE = 0.2` (`config.py:88`), not covered by this row.
**If it were reversed:** Raising the values back would refuse more real claps and send users to `--clap-threshold` or hand-typed times; lowering them further risks locking onto a door slam. Each is a one-line change.
**What you are being asked to confirm:** Needs human research: the values were set by one field failure, not measured over a set of takes; a sweep over the session's recordings reporting which claps pass at 4/2 versus 8/3 would settle it. Planned direction: since a clap or chirp is always required and never guessed, these thresholds decide how often a user is forced to the chirp or to `--sync`, so they matter more, not less.
**Related rows:** refines D-008; D-046 is the per-run multiplier; the sheet notes the config comment date (10-19) and commit date (10-18) disagree.

### D-046 · `--clap-threshold` (default 1.0) scales both loudness thresholds for one run but not the rise time; a failed search reports the sharpest sound against each test and suggests halving the multiplier
**What it means for a user:** When the clap is reported as too quiet, the error tells you the time of the loudest sharp sound, how it scored on each test, and suggests rerunning with half the threshold (the desktop tester has the same field, 0.05 to 10) [VERIFIED, `sync.py:143-151`; `desktop/src/renderer/index.html:49-50`; `docs/procedures/filming.md:240`].
**What it affects in the code:** `run_pipeline.py:359, 414-415` (must be positive), `check_videos.py:61-72`, `sync.py:112-113`; recorded as `sync.clap_threshold` in the metrics [STATED from the row, not re-checked]. The same multiplier now also scales the chirp score (`config.py:85-88`, `chirp.py:118`) [VERIFIED]. "Where" lines have drifted but every behaviour holds.
**If it were reversed:** Without the multiplier the only escape from a quiet clap is typing times by hand; without the diagnostic text the user cannot tell a quiet clap from a missing one.
**What you are being asked to confirm:** Needs human research or `out of scope`: the "suggest half" rule is a rule of thumb; the error text is now documented in filming.md's troubleshooting table, so changing it is a documented-message change. Planned direction: this stays the sanctioned way to accept a faint clap; the never-guess rule means a run with no passing clap or chirp must still stop or record a fallback, never pick a sound silently.
**Related rows:** D-045 (the thresholds it scales), D-008, D-030 (metrics field).

---

## Group 3: How the result is computed (calibration, scale, floor, triangulation, smoothing, skeleton, and how stage 1 runs)

### D-003 · The aniposelib library does the triangulation, the bundle adjustment (joint refinement of all camera positions) and the ChArUco board fallback
**What it means for a user:** Nothing visible directly; it decides which third-party code turns 2D joints into 3D and refines the cameras, and it is one of the packages a setup must install [VERIFIED, `backend/mocap_pipeline/requirements.txt:2`, `backend/requirements.txt:2` pins 0.8.0].
**What it affects in the code:** `calibrate.py:40-58` converts between our rig and aniposelib's `CameraGroup`; `:208` and `:278-299` call `bundle_adjust_iter(only_extrinsics=True)`; `triangulate.py:44` calls `cgroup.triangulate` (the row's `:52` has moved); `board_calibration.py:18-19` imports its board classes [VERIFIED]. Its regularised triangulation and 2D filters are still unused [INFERRED from the calls above].
**If it were reversed:** Replacing it with plain OpenCV plus scipy least squares or a hand-written weighted DLT would remove a dependency and allow confidence weighting (D-004) but means writing and testing bundle adjustment ourselves.
**What you are being asked to confirm:** Needs human research: the sheet asks for a comparison against OpenCV+scipy, pycolmap and a hand-written DLT on `tests/synthetic_scene.py`. Planned direction: dropping the board removes one of its three uses, which weakens the case for keeping it.
**Related rows:** D-004 (unweighted triangulation is aniposelib's), D-011 (board), D-030 (bone-length variability measure comes from the same paper).

### D-004 · Every camera counts equally in triangulation; confidence only decides whether a view is used at all (below 0.5 it is ignored)
**What it means for a user:** A phone that sees a joint poorly but above 0.5 confidence pulls the 3D point as hard as one that sees it well; the pipeline compensates afterwards by dropping the single worst view when the reprojection error is over 15 px [VERIFIED, `triangulate.py:42, 45-61`].
**What it affects in the code:** `triangulate.py:42` applies `TRIANGULATION_MIN_CONFIDENCE` (`config.py:133`); the confidence-weighted version is still a `NotImplementedError` stub at `triangulate.py:17-23` (the row says `:15` and `:49`; both have moved a few lines) [VERIFIED].
**If it were reversed:** Weighting by confidence could lower error when one camera is far or blurred, but RTMPose scores are not probabilities (D-007), so weights would mean different things per detector.
**What you are being asked to confirm:** Needs human research: run `tests/synthetic_scene.py` with and without confidence weighting and compare MPJPE (mean per-joint position error).
**Related rows:** D-003, D-014 (the 0.5), D-015 (the 15 px drop rule), D-007 and D-021 (what the confidence numbers mean per model).

### D-005 · MediaPipe PoseLandmarker, heavy model, is the default 2D joint detector
**What it means for a user:** Unless you pick RTMPose, every frame goes through MediaPipe's heaviest model, which runs on CPU without a GPU and ships with the repo (`backend/models/pose_landmarker_heavy.task`) [VERIFIED, `config.py:7-9`].
**What it affects in the code:** `config.py:9` (the row's `:10`), `backends.py:58` (`MediaPipeBackend`, the row's `:53`), and `DEFAULT_BACKEND` used by `run_pipeline.py:357` [VERIFIED]. The desktop select lists "MediaPipe (default)" (`index.html:38`).
**If it were reversed:** Making RTMPose the default would change every saved joints file's fingerprint (D-023) and the meaning of every confidence threshold (D-014), so it needs the D-039 comparison first.
**What you are being asked to confirm:** That the BlazePose paper (Bazarevsky et al. 2020) describes the model behind PoseLandmarker; citation not checked. The sheet notes the comparison can now be run.
**Related rows:** D-006 (its 33 landmarks are the contract), D-007 and D-022 (the alternative), D-039 (comparison procedure).

### D-006 · The 33 MediaPipe landmarks, in MediaPipe's order, are the data contract between every stage
**What it means for a user:** Every joints file, the `out3d.json` download (D-062) and the 2D keypoints API (D-032) list joints in this fixed order; any other detector must be squeezed into it, and RTMPose fills only 21 of the 33 [VERIFIED, `joints.py:8-21`, `backends.py:115-132`].
**What it affects in the code:** `joints.py:8` ("Do not reorder"), `NUM_JOINTS` at `:20`, `JOINT_INDEX` at `:21`; `schemas.py` not re-opened [VERIFIED for joints.py]. The row's `joints.py:11` is now `:8-9`.
**If it were reversed:** A model-neutral joint set (for example the 17 H36M joints the rig already uses, D-018) would make adding detectors cleaner but would break every saved `.npz` and the API contract.
**What you are being asked to confirm:** Needs human research: decide whether the contract should be model-neutral before a third detector arrives.
**Related rows:** D-005, D-007, D-021 (the mapping into these slots), D-018 (rig built from them), D-032 and D-062 (exposed to users).

### D-007 · RTMPose (Halpe-26 body-with-feet model via rtmlib on ONNX Runtime) is the second detector; the largest detected person is taken as the performer
**What it means for a user:** You can choose RTMPose in the desktop tester or with `--detector rtmpose`; if several people are in shot, the biggest box wins, so a bystander close to a camera can be mistaken for the performer [VERIFIED, `backends.py:177-185`, `:241`].
**What it affects in the code:** `RTMPoseBackend` is now at `backends.py:236` and `pick_person` at `:177` (the row's `:159` and `:149` have moved far, because PR #110 added mode, device and tracking options at `:188-234` and `config.py:24-38`). Scores are clipped to 0..1 at `backends.py:150` (the row's `:138`) [VERIFIED].
**If it were reversed:** Dropping RTMPose leaves MediaPipe alone, which has no person detector and so no bystander problem but also no second opinion for D-039.
**What you are being asked to confirm:** That Jiang et al. 2023 is the RTMPose paper; citation not checked. The largest-box rule needs a decision: a test with two people in frame would show whether it ever picks the wrong one.
**Related rows:** D-005, D-021 (mapping), D-022 (mode), D-014 (thresholds tuned on MediaPipe scores), D-023 (fingerprint).

### D-009 · All cameras are resampled onto a shared 30 fps timeline after sync
**What it means for a user:** Whatever you record at (the protocol asks for 60 or 120 fps), the 3D result and the BVH come out at 30 frames per second; faster footage only helps sync precision and detection, not the output rate [VERIFIED, `config.py:43-44`, `sync.py:284`].
**What it affects in the code:** `config.py:44` (the row's `:19`), `sync.py:269-290` builds the common timeline; the Butterworth cutoff must stay below 15 Hz because of it (D-042); jitter per frame² depends on it (D-044) [VERIFIED].
**If it were reversed:** Following the slowest camera's rate (or the fastest) would keep more motion detail for punches but make the output rate vary per take and shift every threshold that is "per frame".
**What you are being asked to confirm:** Needs human research: whether the target should follow the slowest camera; set C of the take plan (D-036) exists to test exactly this.
**Related rows:** D-036, D-042, D-044, D-063 and D-074 (which fps gets shown).

### D-010 · Cameras are calibrated from the performer's own joints (essential matrix on the best pair, solvePnP for the rest, bundle adjustment with lenses fixed): our method, not Liu et al. 2022
**What it means for a user:** No checkerboard: the performer's short walk with arms and legs stretched is the calibration, and iPhones' lens data from the file replaces any factory numbers [VERIFIED, `calibrate.py:1-22`].
**What it affects in the code:** `calibrate.py:1-16` states the method and that Liu et al.'s intrinsic refinement is unimplemented (`:169-171`); `calibrate_rig` at `:235`; constants in `config.py:95-115` (the row's `config.py:36`). Since the seed, `CALIB_CONVERGENCE_PX` and `CALIB_MAX_ITERATIONS` were removed as unused (7397631, 2026-10-22), which is why the lines moved [VERIFIED].
**If it were reversed:** Implementing Liu et al.'s intrinsic refinement would help non-iPhone cameras (D-037) but risks drifting iPhone lenses that are already correct.
**What you are being asked to confirm:** Needs human research: why fixing the lens is better for phones is written nowhere; the package docstring still credits Liu et al. (not re-checked this session). Hartley and Zisserman for the essential matrix and PnP is textbook; citation not checked.
**Related rows:** D-014 (0.8 calibration confidence from Liu's "data selection"), D-015 (error limits), D-011 (fallback), D-037 (fov seed).

### D-011 · A printed ChArUco board (a checkerboard with markers) is the calibration fallback when the performer-based calibration fails or is too inaccurate
**What it means for a user:** If calibration from the performer fails or its mean error is over 10 px, the run stops and asks you to film the board with every camera and rerun with `--charuco-videos cam0_board.mp4 ...`; in practice that means a second filming session [VERIFIED, `run_pipeline.py:128-147`].
**What it affects in the code:** `stage2_reconstruct/board_calibration.py` (7x5 squares of 30 mm, `:23-26`), loaded only on fallback at `run_pipeline.py:140`; the rig records `{"board": error}` at `:147` [VERIFIED]. "Where" holds.
**If it were reversed:** Without the board, a bad calibration has to be handled by recording the error and continuing (the planned direction), or by asking for a better walk; you lose the one path that does not depend on the detector.
**What you are being asked to confirm:** Whether Garrido-Jurado et al. 2014 (the ArUco marker paper) is the right source for a ChArUco board; citation not checked, but ChArUco builds on ArUco so the lineage is plausible [INFERRED]. Planned direction: this row would be rejected, with D-015's 10 px threshold turned from a "fall back" into a "record and continue" rule, and D-003's board use removed.
**Related rows:** D-003 (aniposelib's board classes), D-015 (the 10 px trigger), D-010.

### D-012 · Real-world scale comes from the performer's stated height, measured heel to ear in upright frames, plus fixed offsets of 0.12 m (ears to skull top) and 0.03 m (heel landmark above the floor)
**What it means for a user:** The height you type is the only thing that makes the skeleton life-sized; a wrong height scales everything, and the two offsets mean the pipeline assumes every adult's skull top sits 12 cm above the ears [VERIFIED, `scale_floor.py:53-71`, `config.py:118-122`].
**What it affects in the code:** `scale_floor.py:69` (exactly as the row says) computes `heel_to_ear_m = height - 0.12 - 0.03`; the constants moved from `config.py:69` to `:121-122` [VERIFIED]. Height must have 10 upright frames (D-035).
**If it were reversed:** A known object or a measured camera baseline would remove the dependence on honesty about height but adds a filming step; dropping the offsets would make everyone about 15 cm short.
**What you are being asked to confirm:** Needs human research: source the two offsets from an anthropometric table (for example head height above the tragion), and state the population. Planned direction: if a BVH must always be produced, a take with no usable upright frames needs a recorded fallback scale (for example 1 unit = 1 m, flagged in the metrics).
**Related rows:** D-035 (the pose), D-040 (height range), D-013 (the same heel offset places the floor), D-075 (which performer's height the Django path uses).

### D-013 · The floor is a plane fitted to the lowest 20% of heel and toe positions; axes are Y up, origin under the performer's feet, Z pointing toward camera 0
**What it means for a user:** In the viewer and in Blender the skeleton stands on Y = 0, faces the viewer (camera 0's side) and starts at the origin; if the floor fit is wrong the character sinks or floats [VERIFIED, `scale_floor.py:8-11, 74-117, 122-148`].
**What it affects in the code:** `scale_floor.py:92-99` takes the lowest `FLOOR_LOWEST_FRACTION = 0.2` (`config.py:129`, the row's `:79`); `:139-148` builds Z toward camera 0 [VERIFIED]. The BVH writer assumes the same Y-up convention (`bvh_writer.py:30`) and the placement tool's constraints use it (`anneal.py:23-24`).
**If it were reversed:** Z-up (Blender's native) would need a conversion on export; a different fraction changes how a jump or a lifted foot biases the floor.
**What you are being asked to confirm:** Needs human research for the 20% (a tuned constant; test with a take that includes a jump); the axis convention may be `out of scope`, as the sheet suggests. Planned direction: a failed floor fit should become a recorded fallback (for example a floor at the lowest heel), not a stop.
**Related rows:** D-012 (shares `HEEL_ABOVE_FLOOR_M`), D-018 (BVH axes), D-008 and D-072 (camera 0 as reference), D-021 (foot tip filled from the big toe feeds this fit).

### D-014 · Confidence cut-offs: 0.8 for a joint to count as a calibration point, 0.5 for a view to count in triangulation
**What it means for a user:** Calibration uses only joints both cameras are very sure about; 3D uses any view above half confidence. If a detector scores low (RTMPose's scores are not probabilities), calibration can run short of points and fail with "need 200 (the performer should move around more)" [VERIFIED, `calibrate.py:74, 129-141`; `triangulate.py:42`].
**What it affects in the code:** `config.py:101` and `:133` (the row's `:41` and `:86`) [VERIFIED]. The frontend's per-camera view, when it existed, drew bones under 0.5 faint (D-032).
**If it were reversed:** Lower cut-offs admit more but noisier points; higher ones fail more takes at calibration. Each is a one-line change, but the meaning differs per detector.
**What you are being asked to confirm:** Needs human research: Liu et al. 2022 section 3 is cited for the 0.8 (citation not checked); nothing for the 0.5. A sweep over both values on a real take per detector would settle it.
**Related rows:** D-010, D-004, D-007 and D-021 (score meaning), D-032.

### D-015 · Pixel error limits: 3 px for RANSAC inliers during pair calibration, drop a view above 15 px during triangulation, fall back to the board above 10 px mean calibration error
**What it means for a user:** A camera that moved or has the wrong field of view shows up as a large calibration error, and above 10 px the run stops with "error X px is above --max-error" and asks for the board or `--recalibrate` [VERIFIED, `run_pipeline.py:128-137`, `docs/procedures/filming.md:245`].
**What it affects in the code:** `config.py:103` (RANSAC), `:115` (board trigger, also `run_pipeline.py:351` default `max_error_px`), `:140` (view drop, used at `triangulate.py:45-66`); the row's `:43`, `:92`, `:65` have all moved [VERIFIED].
**If it were reversed:** A tighter 10 px would fail more real takes; a looser one lets a moved phone through and produces a skewed skeleton with no warning except the metrics.
**What you are being asked to confirm:** Needs human research: the synthetic benchmark gives 0.1 to 3 px, so 10 is "loose by design"; real takes should give the distribution. Planned direction: with the board gone, the 10 px limit becomes a quality flag written to the metrics while the run continues to a BVH, so its value matters as a warning threshold, not a stop.
**Related rows:** D-011, D-010, D-031 (3 px as the quality bar), D-050 (3 and 10 px borrowed for triangulation colours).

### D-016 · Gaps of up to 10 frames in a joint's track are filled by straight-line interpolation; longer gaps stay missing
**What it means for a user:** A joint hidden for a third of a second is drawn as a straight slide between the two ends; hidden longer, it is left empty in `out3d.json` and the BVH gets whatever stage 3 does with missing joints (not checked here) [VERIFIED, `smooth.py:23-53`].
**What it affects in the code:** `smooth.py:26, 44, 49` and `config.py:137` (the row's `:90`); the number of long gaps is printed at `:53` [VERIFIED].
**If it were reversed:** Filling longer gaps invents motion; filling none leaves more holes for the smoother to break runs on (D-017, D-042 work "per continuous run").
**What you are being asked to confirm:** Needs human research: no rationale recorded; a test with a known occlusion length would show where interpolation starts to look wrong. Planned direction: if every run must end in a BVH, what happens to joints that stay missing needs its own recorded rule.
**Related rows:** D-017 and D-042 (filters run per run between gaps), D-030 (`missing_fraction`).

### D-017 · Savitzky-Golay smoothing (a sliding polynomial fit) with a 7 frame window and order 2, per continuous run, is the default
**What it means for a user:** Small jitter is removed while a punch, which lasts only a few frames at 30 fps, is meant to survive; it is the default in the desktop tester's Smoother select [VERIFIED, `config.py:141-150`, `desktop/src/renderer/index.html:44`].
**What it affects in the code:** `smooth.py:60-71` (the row's `:50`), `config.py:143-144` (the row's `:95`) [VERIFIED].
**If it were reversed:** Butterworth (D-042) is the alternative already built; a larger window would smooth more and flatten fast moves.
**What you are being asked to confirm:** The Savitzky and Golay 1964 citation covers the filter, not the window or order; citation not checked. The window and order need a comparison on real fast takes (D-051 is the procedure).
**Related rows:** D-042 (second smoother), D-043 (how one is chosen), D-044 (jitter measure), D-051.

### D-018 · The rig is the 17 joint Human3.6M skeleton, built with video2bvh's rules, exported as BVH in centimetres with ZXY rotation channels
**What it means for a user:** The BVH opens as-is in Blender and in three.js viewers; spine, neck and head are approximations from hips, shoulders and ears, and limb twist (rotation about the bone's own axis) is not recovered [VERIFIED, `joints.py:31-45`, `stage3_rig/bvh_writer.py:30, 43`, `stage3_rig/rotations.py:1-4`].
**What it affects in the code:** `joints.py:31-89` (`RIG_JOINT_SOURCES`, `RIG_PARENTS`; the row's `:60` is within this block), `stage3_rig/skeleton.py:1-3`, `bvh_writer.py:124` (metres to cm) [VERIFIED].
**If it were reversed:** A 33 joint rig would keep MediaPipe's hands and face but no standard viewer rig matches it; FBX is out of scope (D-062).
**What you are being asked to confirm:** That Ionescu et al. 2014 defines the 17 joint skeleton; citation not checked. video2bvh is software (MIT), noted in each file header.
**Related rows:** D-006 (source joints), D-013 (axes), D-030 (bone-length variability is measured on this rig), D-062 (download), D-074 (stored in Django).

### D-021 · RTMPose's 26 Halpe joints are mapped by name into the 33 MediaPipe slots; the foot tip slot is filled from the big toe; the 12 face and finger slots stay empty; a joint scored 0 or less becomes empty
**What it means for a user:** With RTMPose, the result has no eyes, mouth or fingers (nothing downstream uses them) and the "foot index" is really the big toe, which only the floor fit uses [VERIFIED, `backends.py:104-132, 138-152`].
**What it affects in the code:** The name map at `backends.py:115-132` (the row's `:117`), the clip and NaN rule at `:150-151` (the row's `:147`) [VERIFIED]. The floor fit reads `LEFT_FOOT_INDEX`/`RIGHT_FOOT_INDEX` (`scale_floor.py:92`).
**If it were reversed:** A model-neutral contract (D-006's open question) would remove the mapping; keeping it means every new model needs a similar table.
**What you are being asked to confirm:** That Fang et al. 2023 (AlphaPose) plus the Halpe-FullBody README define the 26 point order; citation not checked. Whether big toe for foot tip measurably moves the floor (D-013) has not been tested.
**Related rows:** extends D-006 and D-007; D-013; D-014 (the 0-or-less cut-off sits under the 0.5).

### D-022 · RTMPose runs in rtmlib's "balanced" mode on CPU (YOLOX-m person detector plus RTMPose-m joints), rtmlib pinned to 0.0.16, onnxruntime unpinned, models downloaded on first run
**What it means for a user:** The first RTMPose run needs the network to fetch the models; it runs on CPU unless you ask for the GPU; "balanced" is a middle choice between speed and accuracy [VERIFIED, `config.py:24-28`, `backends.py:188-193, 236-276`].
**What it affects in the code:** The row is partly out of date: since PR #110 the mode is `config.RTMPOSE_MODE` (`config.py:28`) with `--rtmpose-mode`, a `--rtmpose-device cpu|cuda` option (`backends.py:214-234`) and a tracking option that runs the person detector only every N frames (`config.py:35-38`), none of which has a row. `rtmlib==0.0.16` is at `mocap_pipeline/requirements.txt:8` and also in `backend/requirements.txt:36`; `onnxruntime` is unpinned in the first and pinned to 1.31.0 in the second [VERIFIED].
**If it were reversed:** "performance" mode (RTMPose-x at 384x288) costs time per frame for unknown gain on real takes; exposing the options is now done, so the open choice is the default.
**What you are being asked to confirm:** The sources describe the software, not the choice; citation not checked. A new row `from D-022` for the mode/device/tracking options would keep the sheet current.
**Related rows:** refines D-007; D-023 (settings now in the fingerprint); D-070 (second requirements file).

### D-042 · A Butterworth low-pass smoother (cutoff 8 Hz, order 2, run forward and backward so it has no lag) is the second smoother; runs shorter than the filter's padding are left unfiltered; a cutoff at or above half the frame rate is an error
**What it means for a user:** Picking "Butterworth low-pass" removes everything faster than 8 cycles per second; at the 30 fps timeline the limit it must stay under is 15 Hz [VERIFIED, `smooth.py:74-90`, `config.py:151-156`].
**What it affects in the code:** `smooth.py:74` as the row says; constants at `config.py:155-156` (the row's `:109`) [VERIFIED]. The config comment itself quotes Winter 2009 and says "starting guess, not measured".
**If it were reversed:** Dropping it leaves Savitzky-Golay alone and removes the comparison D-043 was built for; a lower cutoff (Winter's 6 Hz) would flatten punches.
**What you are being asked to confirm:** Winter 2009 chapter 3 supports the filter type for human movement; citation not checked. The 8 Hz and order 2 need the D-051 comparison on real fast takes.
**Related rows:** extends D-017; D-043, D-044, D-009 (Nyquist depends on the 30 fps), D-051.

### D-043 · The smoother is chosen per run (`--smoother savgol|butterworth`, default savgol, same select in the desktop tester); smoothing always reruns under `--resume`; the choice and settings are written to the metrics
**What it means for a user:** Switching smoother on a finished take takes seconds, because only smoothing and the rig are redone; the metrics file says which one ran [VERIFIED, `run_pipeline.py:358, 410-412`, `smooth.py:93-120`, `desktop/src/renderer/index.html:43-46`].
**What it affects in the code:** `config.py:150` (the row's `:104`), `smooth.py:105-106, 120` record `smooth.method`, `smooth.settings`, `smooth.runs_too_short` [VERIFIED].
**If it were reversed:** A fixed smoother would simplify the UI and the metrics but make the D-051 comparison a code change each time.
**What you are being asked to confirm:** Needs human research or `out of scope` (engineering choice); the outcome of the smoother comparison should become a row `from D-017` and D-042.
**Related rows:** D-017, D-042, D-030 (metrics keys), D-051 (procedure), D-023 (same pattern as `--detector`).

### D-047 · Stage 1 detects several videos at once in separate spawned processes; the command line defaulted to one per video, `run()` to one at a time (superseded)
**What it means for a user:** Historically, the desktop tester and the command line ran videos in parallel while the API did not; D-048 replaced that split.
**What it affects in the code:** The machinery is at `run_pipeline.py:271-325` (`_detect_videos`, `ProcessPoolExecutor` with `spawn` at `:317-318`); the row's `:186`, `:204`, `:627`, `:684` are all stale [VERIFIED]. The knock-on it recorded for the progress bar was fixed by D-049's "Detected joints in" line (`desktop/src/shared/progress.ts:106-118`).
**If it were reversed:** One video at a time is simpler and uses one model's memory but makes a 4 camera take four times slower.
**What you are being asked to confirm:** The Python docs support `spawn` on macOS only, as the sheet says; citation not checked. Superseded, so the verdict matters mainly as a training example.
**Related rows:** to D-048; D-020 (same spawn reasoning), D-033, D-041, D-049, D-057.

### D-048 · Stage 1 runs one process per video, capped at the CPU core count and at 4 (`DETECT_JOBS = 0` automatic), for the command line, the desktop tester and the API alike
**What it means for a user:** A 4 camera take detects all four videos at once on a 4 core machine, using roughly 1 to 2 GB per process; the desktop tester exposes "Videos detected at once" (0 = automatic, up to 16) [VERIFIED, `config.py:10-16`, `run_pipeline.py:212-223`, `desktop/src/renderer/index.html:55`].
**What it affects in the code:** `config.py:15-16` as the row says; `detect_jobs` at `run_pipeline.py:212` (the row's `:183`); the API calls `run()` without `jobs` at `api.py:206` (the row's `:200`) and so inherits the automatic default [VERIFIED].
**If it were reversed:** A fixed 1 would protect memory on small laptops at the cost of wall time; removing the cap of 4 risks oversubscription since MediaPipe already uses several cores (mac-setup.md footnote 9, [STATED]).
**What you are being asked to confirm:** The `ProcessPoolExecutor` docs support the core-count cap only; citation not checked. The 4 and the 1 to 2 GB figure need a measurement on one machine.
**Related rows:** from D-047; D-020 (the API worker now spawns its own pool), D-030 (per-camera timings overlap), D-041, D-057.

### D-049 · A video that fails in stage 1 does not stop the others; failures are printed and saved as `stage1.failed`; the run stops after stage 1 with a summary; if every video failed the same way the summary blames the setup
**What it means for a user:** You learn about every bad video in one run instead of one per run, keep the joints of the good ones for `--resume`, and get told when the cause is your Python environment rather than the files [VERIFIED, `run_pipeline.py:284-288, 540-563`].
**What it affects in the code:** `_detect_worker` at `run_pipeline.py:252` (the row's `:242`), `metrics.record("stage1.failed")` at `:547`, the same-error heuristic at `:560-563`; the desktop tester parses "Detection failed for" at `progress.ts:121` and "Detected joints in" at `:114` [VERIFIED].
**If it were reversed:** Stopping at the first failure is simpler but wastes the detection time of the other videos.
**What you are being asked to confirm:** Needs human research or `out of scope`: the same-error heuristic is a rule of thumb; it is wrong when all videos genuinely share a fault (for example all muted).
**Related rows:** D-048, D-030 (metrics field), D-033 and D-020 (printed-line coupling), D-023 (resume).

---

## Group 4: What the result looks like and how its quality is measured (files, metrics, BVH)

### D-023 · A saved joints file records which detector made it; `--resume` reuses it only for the same detector; files without the field count as MediaPipe
**What it means for a user:** Rerunning with the other detector re-detects instead of silently reusing the wrong joints; old files from before `--detector` existed are treated as MediaPipe [VERIFIED, `run_pipeline.py:508-521`].
**What it affects in the code:** The check is now at `run_pipeline.py:511-525` (the row's `:189`, `:201`) and `io.py:88` (the row's `:84`). Since PR #110 the fingerprint also carries `detector_settings` (mode, device, detect-every) and re-detects when they differ (`run_pipeline.py:197-210, 521-525`), which answers the sheet's note that mode changes would not re-detect; model version and weights are still not recorded [VERIFIED].
**If it were reversed:** Without the field, a `--resume` after switching detector would mix joints from two models with different confidence scales.
**What you are being asked to confirm:** Needs human research or `out of scope` (data contract, engineering choice). The AiiDA provenance lead is a lead, not a citation.
**Related rows:** D-005, D-007, D-022, D-032 (keypoints files are what the API serves), D-074 (the Django path deletes these files).

### D-030 · Quality without ground truth is measured by reprojection error, bone-length variability, missing fraction, views per joint and per-stage timing, written as nested keys to `<out>.metrics.json` with a time-stamped `<out>.log`, also on failure, and served at `GET /takes/{id}/metrics.json`
**What it means for a user:** Every run leaves a numbers file and a log next to the output; the desktop tester's result panel and the procedures read nothing else; there is no "accuracy" figure because nothing in the field knows the truth [VERIFIED, `metrics.py:1-25`, `io.py:36-46`, `api.py:565-572`].
**What it affects in the code:** `metrics.py:60-84` (record, time), `pose_summary` at `:104` (the row's `:116`), `bone_length_summary` at `:148`; the API route moved from `api.py:559` to `:565` [VERIFIED]. The Django path stores the same JSON as a field (D-074).
**If it were reversed:** Dropping any key breaks the desktop panel (`desktop/src/shared/metrics.ts` reads them by name) and the procedures; this is the one contract that most tools share.
**What you are being asked to confirm:** The measures are sourced (Zhang 2000 for reprojection error, Triggs et al. 2000 for bundle adjustment, Karashchuk et al. 2021 for limb-length variability); the module docstring repeats the same DOIs. Citations not checked. The file layout and key names are ours and need only a decision.
**Related rows:** D-031 (cut-offs), D-044, D-043, D-046, D-049 (fields added later), D-050, D-074.

### D-031 · Take-quality thresholds: calibration error under 3 px, bone-length standard deviation under 0.01 m (0.02 bad), missing fraction under 0.05 (0.15 bad), 30 or more upright frames (under 10 bad)
**What it means for a user:** These are the green and red colours in the desktop result panel and the "what good looks like" table in the procedures; a value exactly on a red limit shows red even though the pipeline accepted it [VERIFIED, `desktop/src/shared/metrics.ts:103-107`, `docs/procedures/processing-a-take.md:66-69`, `desktop-tester.md:59-62` and footnote 14].
**What it affects in the code:** The row's `desktop/src/renderer/main.ts:226` is stale: the thresholds now live in `desktop/src/shared/metrics.ts:103-107` (`grade(x, 3, 10)`, `grade(mm, 10, 20)`, `grade(upright, 30, 10)`); the README line is now `backend/mocap_pipeline/README.md:103` and the procedure's is `:66-69` [VERIFIED].
**If it were reversed:** Looser limits hide moved phones; tighter ones colour every real take red until the first session shows what is normal.
**What you are being asked to confirm:** Needs human research: the measures are sourced in D-030, the cut-offs are team judgement plus the synthetic benchmark; the first real session's distribution would settle them. Note the duplication across three files.
**Related rows:** D-030, D-015 (3 px and 10 px), D-035 (10 frames), D-050 (more colours in the app).

### D-032 · The 2D keypoints API: `GET /takes/{id}/keypoints.json` lists cameras; `GET /takes/{id}/keypoints/{camera}.json` gives per-frame pixel points (0.1 px), confidence (3 decimals) and timestamps (4 decimals) with the clap time to subtract; only for done or failed takes
**What it means for a user:** A per-camera overlay view can show what each phone saw, with t = 0 at the clap; no such view is routed in the current web app (the `CameraView2D` component exists but no route reaches it) [VERIFIED, `api.py:575-640`; `frontend/src/app/routes.tsx:16-44` has no viewer route; `frontend/src/lib/api.ts:64-72`].
**What it affects in the code:** The routes are now at `api.py:607` and `:628` (the row's `:582`, `:601`); rounding at `:600-604`; the done-or-failed guard at `:558-561` [VERIFIED].
**If it were reversed:** Without the endpoint the only way to see 2D joints is the `.npz` files on disk.
**What you are being asked to confirm:** Needs human research or `out of scope` (engineering contract). Joint order is D-006; the frontend's faint-under-0.5 rule restates D-004.
**Related rows:** D-006, D-004, D-020 (take folders), D-023 (the files it reads), D-074 (the Django path deletes them).

### D-039 · A detector comparison uses at least three takes (calm, fast, partially occluded), each detector in its own output and calibration folder, compared on model-independent metrics only
**What it means for a user:** To decide MediaPipe versus RTMPose you run both on the same three takes into separate folders and compare error, missing fraction, bone spread and timing, never mean confidence [VERIFIED, `docs/procedures/comparing-pose-models.md:7-11, 44-45`].
**What it affects in the code:** Nothing; a procedure. "Where" holds [VERIFIED].
**If it were reversed:** One take measures that take; sharing folders would mix sync and calibration from two detectors.
**What you are being asked to confirm:** Needs human research or `out of scope`; its outcome is meant to become a row `from D-005` and D-007.
**Related rows:** D-005, D-007, D-036 (the take plan supplies the three kinds), D-030.

### D-044 · Smoothness is measured as `jitter_mm`: the mean size of each joint's frame-to-frame acceleration (mm per frame squared), in `pose_raw` and `pose_final`, compared between runs of one take only
**What it means for a user:** The desktop panel shows "jitter before → after smoothing (N % less)"; real motion contributes too, so a punch take has higher jitter than a walk and the number is meaningless across takes [VERIFIED, `metrics.py:124, 132-137`, `desktop/src/shared/metrics.ts:203-215`].
**What it affects in the code:** `metrics.py:132` (the row's `:117`) and `:124` [VERIFIED]. Its unit depends on the 30 fps timeline (D-009).
**If it were reversed:** A per-second unit (as in the cited paper) would be frame-rate independent at the cost of a conversion.
**What you are being asked to confirm:** That Kanazawa et al. 2019 reports mean joint acceleration as a smoothness measure; citation not checked. The per-frame unit is a choice to confirm.
**Related rows:** extends D-030; D-009, D-042, D-043, D-050 (the 40 % / 10 % colours), D-051.

### D-051 · Smoothers are compared by rerunning one take with `--resume` and the other smoother, then reading a side-by-side table; "lower jitter with the same bone spread is the better filter for that take"
**What it means for a user:** One button in the desktop tester does the rerun; you then pick by the rule, but the rule cannot see a punch that was flattened, so you must also watch the fast moments [VERIFIED, `docs/procedures/desktop-tester.md:67`, `desktop/src/renderer/main.ts:435-438`, `backend/mocap_pipeline/README.md:59`].
**What it affects in the code:** The rerun at `main.ts:435-438` (resume on, recalibrate off, smoother swapped); the procedure line moved from `desktop-tester.md:61` to `:67` [VERIFIED].
**If it were reversed:** A ground-truth measure (MPJPE) is only available on the synthetic scene, so any field rule is a proxy.
**What you are being asked to confirm:** Needs human research or `out of scope`: jitter rewards over-smoothing; a peak-loss check (for example maximum hand speed before and after) would make the rule safer.
**Related rows:** D-043, D-044, D-017, D-042, D-039 (same pattern).

---

## Group 5: The desktop tester

### D-033 · Stage 1 prints `progress: detect <video> <i>/<n>` every 30 frames when `MOCAP_PROGRESS` is set, and the desktop tester parses that line for its bar
**What it means for a user:** The per-video progress in the tester comes from these lines; the frame total is the container's estimate, so "frame 1790 of 1800" can end a few frames early or late [VERIFIED, `detect.py:47-50, 82-83`, `desktop/src/shared/progress.ts:87-103`].
**What it affects in the code:** `detect.py:50` and `:83` (the row's `:44`, `:81`); the tester sets `MOCAP_PROGRESS: '1'` at `desktop/src/main/pipeline.ts:19` [VERIFIED]. A renamed print freezes the bar; the desktop tests replay these lines to catch that (`docs/procedures/testing-the-backend.md:15`).
**If it were reversed:** A structured progress channel (JSON lines or a file) would be sturdier than parsing prints but is a bigger change across D-020, D-049 and this row.
**What you are being asked to confirm:** Needs human research or `out of scope`: the 30 frame interval has no recorded reason; it only trades log length for bar smoothness.
**Related rows:** extends D-020; D-041, D-047, D-049, D-058 (the tests that guard it).

### D-041 · The tester's progress bar gives detection 75 % (split evenly across videos), sync 5 %, calibration 8 %, triangulation 5 %, writing 7 %
**What it means for a user:** The bar moves mostly during detection and then jumps through the later stages; the weights are guesses, so the bar is a rough guide, not a time estimate [VERIFIED, `desktop/src/shared/progress.ts:13`].
**What it affects in the code:** `progress.ts:13` (the row's `:11`) and the stage transitions at `:141-182` [VERIFIED]. Since D-048 the per-camera timings in `metrics.json` overlap, so they cannot simply be summed to re-derive the weights.
**If it were reversed:** Measured weights from a few takes' `timing` block would make the bar honest at the cost of reading real data first.
**What you are being asked to confirm:** Needs human research or `out of scope` (UI constant); the `timing` block of a few real takes gives the real split.
**Related rows:** D-033, D-030, D-048.

### D-050 · The result panel adds three colour rules: mean triangulation error under 3 px green / over 10 px red (borrowed from calibration), jitter reduction over 40 % green / under 10 % red, frames with nobody detected under 5 % green / over 20 % red; it also lists the 4 worst joints and 4 least rigid bones
**What it means for a user:** Colours you read as verdicts; the triangulation colour borrows the calibration limits even though the two errors behave differently, and the jitter colour rewards whichever smoother smooths more [VERIFIED, `desktop/src/shared/metrics.ts:104, 127, 187, 215, 239`; `docs/procedures/desktop-tester.md:103`].
**What it affects in the code:** All four cited lines in `metrics.ts` still match exactly (`:104`, `:127`, `:215`, `:187`) [VERIFIED]. Hard-coded in the app only; the procedures do not repeat these three.
**If it were reversed:** No colour on these rows is honest but less helpful; separate measured limits would need real takes.
**What you are being asked to confirm:** Needs human research: the triangulation limits are an assumption, the nobody-seen limits have no reason recorded; the first real session's values would settle them.
**Related rows:** extends D-031; D-044 and D-043 (jitter depends on the smoother and frame rate), D-015.

### D-057 · Cancel stops the whole process tree: on macOS and Linux the pipeline runs detached in its own process group and gets SIGTERM as a group; on Windows `taskkill /T /F`; either failing falls back to `child.kill()`
**What it means for a user:** Pressing Cancel really stops the detection workers; before this they kept running, held the pipes open and kept writing joints files. On Windows the kill is forced; on a Mac a worker could in principle ignore SIGTERM [VERIFIED, `desktop/src/main/pipeline.ts:93, 120-132`].
**What it affects in the code:** `pipeline.ts:93` (detached on non-Windows) and `:127-132` (the row's `:124`) [VERIFIED]. Guarded by the desktop test named in the row [STATED].
**If it were reversed:** Killing only the parent brings back the orphaned workers; using SIGKILL on POSIX would be surer but skips cleanup.
**What you are being asked to confirm:** The Node and Microsoft documentation describe `detached` and `taskkill /T /F` as the row says; citation not checked. May be `out of scope` as a bug fix.
**Related rows:** follows from D-047 and D-048; D-020.

---

## Group 7: The camera placement tool

### D-019 · Camera placement is scored with Rahimian and Kearney's dynamic-occlusion metric (how many directions a point can be seen from as the performer turns) and optimised by simulated annealing
**What it means for a user:** A separate tool, not part of processing a take, that can say "your coverage is poor on the left" for an existing rig or propose where N phones should stand in a room [VERIFIED, `backend/mocap_pipeline/placement/__init__.py:1-15`].
**What it affects in the code:** `placement/metric.py:30-75` (sees, convergence 40 to 140 degrees, effective range 6 m from `config.py:161-165`), `metric.py:83-130` (point and layout cost), `anneal.py:84-126` (the search). "Where" is the package, which holds; the stubs noted in 2026-10-16 were filled by b35b3e4 [VERIFIED].
**If it were reversed:** A simpler rule (D-025's arc) already covers the common case; the tool adds value only for odd rooms or many phones.
**What you are being asked to confirm:** That the 2015 VRST paper defines the metric as implemented; citation not checked, and the sheet says the paper's own penalty value was not compared (D-026).
**Related rows:** D-026, D-027, D-028, D-029 refine it; D-025 and D-034 use different numbers; D-013 (world axes).

### D-026 · A target point no camera sees costs 360 plus a penalty of 360 degrees (our value for the paper's equation 1 penalty)
**What it means for a user:** Without the penalty the optimiser parks every camera in one spot, since an unseen point cost no more than one everyone sees from the same side [VERIFIED, `config.py:166-170`, `metric.py:87-104`].
**What it affects in the code:** `config.py:170` (the row's `:113`), `metric.py:102` [VERIFIED].
**If it were reversed:** Removing it breaks the optimiser as the comment describes; a different value changes how hard the tool tries to cover every point versus covering most points well.
**What you are being asked to confirm:** Whether the paper gives its own penalty value and how ours compares; citation not checked.
**Related rows:** refines D-019; D-027 (the points being scored), D-028.

### D-027 · The layout is scored on at most 300 joint positions subsampled (seed 0) from a recorded take, or without one on a 7x7x3 grid over the capture volume (half-width 1.5 m, 0.5 m step, heights 0.1, 0.9 and 1.5 m)
**What it means for a user:** With a real take the tool scores where that performer actually went; without one it assumes a 3 m square at three heights, which is a guess at a performer's reach [VERIFIED, `config.py:171-178`, `metric.py:133-150`].
**What it affects in the code:** `config.py:173-178` (the row's `:116`, `:121`), `metric.py:133` (the row's `:141`) [VERIFIED].
**If it were reversed:** More points make the annealer slower (it evaluates the cost thousands of times); a bigger grid covers more floor than one performer uses.
**What you are being asked to confirm:** Needs human research: the grid values are guesses; the paper scored a different target distribution.
**Related rows:** refines D-019; D-026, D-028, D-034 (capture area size).

### D-028 · Annealer schedule: 2000 iterations (paper used 20000), one camera moved per step by a 0.5 m Gaussian step, start temperature 5 % of the initial cost falling linearly to zero, best layout kept; cameras always aim at one fixed point, so the paper's re-aim move is dropped
**What it means for a user:** A run takes tens of seconds in pure Python and gives a good-enough layout; the final answer would need ten times more iterations [VERIFIED, `anneal.py:84-117`].
**What it affects in the code:** `anneal.py:84-85` (defaults) and `:110-117` (temperature, step) as the row says [VERIFIED].
**If it were reversed:** Adding the re-aim move brings back the paper's full method but the tool's model has cameras aimed at a single point by construction (`anneal.py:24`).
**What you are being asked to confirm:** Kirkpatrick et al. 1983 for annealing, Rahimian and Kearney section 3.5 for its use here; citations not checked. The 5 % and 0.5 m have no reason recorded.
**Related rows:** refines D-019; D-026, D-027, D-029 (the constraints it moves within).

### D-029 · Default constraints: tripods anywhere on an 8 m by 8 m floor, lens height 0.8 to 1.8 m, at least 1.5 m from the aim point, aim at (0, 0.9, 0) m, a 1920x1080 image at the default 65 degree field of view
**What it means for a user:** Unless you pass your room's size, the tool assumes a large square room and hip-height aiming; the filming procedure separately says 2 to 4 m away at chest height [VERIFIED, `anneal.py:21-33`, `docs/procedures/filming.md:81`].
**What it affects in the code:** `anneal.py:26-33` (the row's `:26`) [VERIFIED].
**If it were reversed:** Matching the filming protocol's numbers would make the two documents agree at the cost of restricting the search.
**What you are being asked to confirm:** Needs human research: reconcile with D-034 and D-025; measure a real room.
**Related rows:** refines D-019; D-034, D-037 (same default fov), D-013 (axes).

---

## Group 6: The web app and the two servers (FastAPI take folders, Supabase, the Django "MotionBoxPro" backend)

A reviewer's note on this group: the React app's routes (`frontend/src/app/routes.tsx:16-44`) go to landing, login, projects, motions, recordings, streaming and settings, all of which talk to the Django backend. No route reaches `FootagePage` (Supabase footage), the clips list, or the FastAPI client in `src/lib/api.ts`; `frontend/.env.example:1-3` says the same ("Only VITE_DJANGO_URL is read by the pages the app routes to") [VERIFIED]. So D-052 to D-056 describe code that is in the repo but not reachable from the UI.

### D-020 · The FastAPI server runs one take at a time in a spawned worker process; each take is a folder with `status.json` and `log.txt`; stage progress is parsed from printed lines
**What it means for a user:** Takes queue and run one after another; the status and the log are plain files you can open; a server restart marks interrupted takes failed [VERIFIED, `api.py:18-23, 118-123, 164-168, 229, 233-240`].
**What it affects in the code:** The pool at `api.py:229` (the row's `:52`), status writes at `:118` (the row's `:66`), the stdout stand-in at `:164` (the row's `:188`) [VERIFIED]. Since D-048 the single worker starts its own detection pool, so "one at a time" now means one take, several videos.
**If it were reversed:** A proper job queue would survive restarts and allow more than one take, at the cost of a dependency; a structured progress channel would replace the print parsing.
**What you are being asked to confirm:** Needs human research or `out of scope` (engineering choice); the print coupling is fragile and shared with the desktop tester (D-033, D-049).
**Related rows:** D-048, D-033, D-049, D-032, D-064 (web statuses map onto `queued/running/done/failed`, `api.py:200-214`), D-075 (the Django equivalent).

### D-052 · The frontend uses Supabase as a hosted database and file store, configured by `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`; without both the client is null and uploads are off
**What it means for a user:** Today nothing: no routed page uses it (see the note above). If it were wired in, the browser would talk to Supabase directly and anyone with the bundled key could read the buckets [VERIFIED, `frontend/src/lib/clips.ts:6-9`, `routes.tsx`].
**What it affects in the code:** `package.json:15`, `clips.ts:9`, `.env.example:5-6` (the row's `:3`; the file was reorganised around `VITE_DJANGO_URL`), `vite-env.d.ts:7-9` which still declares `VITE_SUPABASE_SECRET_KEY` (a secret must never be a `VITE_` variable) [VERIFIED].
**If it were reversed:** Removing Supabase deletes a second storage path that the Django model (D-072) has already replaced.
**What you are being asked to confirm:** The Supabase client reference describes the library only; citation not checked. The real question is whether to delete this code now that D-070 to D-076 exist.
**Related rows:** D-053, D-055, D-056 depend on it; D-070 and D-071 replaced it.

### D-053 · Raw videos were uploaded from the browser to a public `footage` bucket and recorded in a `footage` table; a row is "waiting" until `take_id` is set
**What it means for a user:** Nothing today (unrouted). The design never deleted a video after processing and set no size limit [VERIFIED, `frontend/supabase/footage.sql:1-25`, `frontend/src/lib/footage.ts:33-47`].
**What it affects in the code:** `footage.sql:1`, `footage.ts:36, 66`, `FootagePage.tsx:47` (the row's `:46`) [VERIFIED].
**If it were reversed:** Already effectively reversed by D-072 and D-076, where recordings live under Django's `MEDIA_ROOT` behind a login.
**What you are being asked to confirm:** Needs human research or `rejected` with D-076 named as the replacement.
**Related rows:** D-052, D-054, D-056, D-076 (replacement).

### D-054 · A take was made by ticking one video per camera; tick order set the camera order; at least 2 videos, `.mov`/`.mp4` only; height default 1.75 m within 1.0 to 2.5; the browser downloaded the videos again and posted them to `POST /takes` (superseded)
**What it means for a user:** Nothing today (unrouted). The notable design point was that the tick order decided which phone is camera 0, and that order was never saved [VERIFIED, `FootagePage.tsx:29-48, 101`, `footage.ts:54-67`, `api.ts:84-91`].
**What it affects in the code:** The cited lines hold except `api.ts:102` (the file is now 100 lines; the upload is at `:84-91`) [VERIFIED].
**If it were reversed:** D-060's Upload spec replaces it on paper and D-072's slot model replaces it in the Django backend.
**What you are being asked to confirm:** Superseded; the verdict matters as a training example. The camera-0 problem recurs in D-072 (slots are assigned by lowest free number, not by the user's order).
**Related rows:** to D-060; D-002 and D-040 restated; D-008 and D-013 (camera 0); D-038.

### D-055 · Finished clips were listed from a Supabase `clips` table with a `source` of ai, suit or review, a free-text duration, and a BVH in a public `clips` bucket played straight from its public URL
**What it means for a user:** Nothing today: no routed page reads `clips`, and the files the row cited for the viewer no longer reference it [VERIFIED, `frontend/src/features/projects/ProjectDetailPage.tsx` is 66 lines with no clips code; `StudioProvider.tsx:35` holds seed recordings only; `clips.ts:11-41` remains].
**What it affects in the code:** `clips.sql:1-24` and `clips.ts` remain; the row's `ProjectDetailPage.tsx:131` and `StudioProvider.tsx:33` are stale (the first file is shorter than 131 lines) [VERIFIED].
**If it were reversed:** The Django `MotionVersion` (D-074) already serves the BVH behind a login, so the public bucket is redundant.
**What you are being asked to confirm:** Needs human research or `rejected` with D-074 as the replacement; the `source` column is the last trace of the suit idea D-061 removed.
**Related rows:** D-052, D-056, D-061, D-018, D-074 (replacement).

### D-056 · Supabase access has no sign-in: both buckets are public, and the anonymous role may list, insert and upload; on `footage` it may update only `take_id` and `project_id`
**What it means for a user:** If the Supabase project is still live, anyone with the URL and publishable key (which ship in any build that includes them) can read every uploaded video and upload files of any size, regardless of whether the app routes there [VERIFIED, `footage.sql:13-25`, `clips.sql:16-24`].
**What it affects in the code:** `clips.sql:16, 23` (the row's `:21`), `footage.sql:13, 18` (the row's `:19`) [VERIFIED]. The column-level grant on `footage` was a deliberate narrowing.
**If it were reversed:** Row-level security tied to a login is what Django now provides (D-071); the cheaper fix is to tear down the buckets.
**What you are being asked to confirm:** Needs human research or `rejected` with D-071 as the replacement; also whether the live project should be closed.
**Related rows:** D-052, D-053, D-055; replaced by D-071.

### D-060 · The Upload screen replaces Record: a take name, a height with a cm/ft selector, and 2 to 4 video files of type `.mp4`, `.mov` or `.avi`, with "Start processing" disabled until all three are set
**What it means for a user:** As specified, you could not add a fifth camera, could pick `.avi`, and could type feet; the API accepts any count from 2, refuses `.avi`, and wants metres, so the spec and the server disagree in three places [VERIFIED, `docs/DESIGN.md:155-157`, `api.py:70-71, 418, 470`].
**What it affects in the code:** A spec, not code: `DESIGN.md:155-157` (the row's `:149`, `:156`, `:157`). The current app has no Upload route; recordings are added one at a time (`routes.tsx:35-39`, D-076) and a motion is assembled from them (D-072) [VERIFIED].
**If it were reversed:** Following the API would mean "2 or more" and `.mov`/`.mp4` only; following the spec would mean adding `.avi` to the API and a cap of 4.
**What you are being asked to confirm:** Needs human research: settle the three conflicts (4 versus no maximum, `.avi`, feet to metres) and whether D-054's footage bucket and tick order are dropped (they are, in effect, by D-072).
**Related rows:** from D-054; conflicts with D-024 and D-001; restates D-040; D-038 and D-076 (file rules); D-073 (same cap in Django).

### D-061 · No Suit/AI/Review distinction anywhere in the UI; the suit calibration bar and the device, scene and integration settings tabs are removed; Settings keeps only Accessibility
**What it means for a user:** The app is camera-only; nothing mentions a suit, and Settings has one tab [VERIFIED, `docs/DESIGN.md:107, 146, 214, 228`].
**What it affects in the code:** A spec; `DESIGN.md` lines hold. `clips.sql:8` still has the `source` column with suit and review [VERIFIED].
**If it were reversed:** Reintroducing sources would need data the pipeline does not produce.
**What you are being asked to confirm:** Needs human research or `approved` as product scope; decide whether to drop `clips.source` with it.
**Related rows:** D-055 (the column), D-062 (same scope cut).

### D-062 · Exports are "Download BVH" (primary) and "Download JSON" (the pipeline's `out3d.json`); FBX, the Rig tab, live streaming and the per-joint confidence panel are out of scope this semester; Motion Library is a disabled placeholder
**What it means for a user:** Two download buttons; the JSON exposes the pipeline's internal 33 joint format (D-006) as a public file; the Streaming route still exists in the router even though the spec removes the tab [VERIFIED, `DESIGN.md:198-205, 230`; `routes.tsx:38`].
**What it affects in the code:** A spec; the Django BVH route is `GET /api/v1/motions/<uuid>/versions/<n>/bvh/` (`motions/urls.py:12-14`); no JSON route was checked [VERIFIED for BVH].
**If it were reversed:** FBX would need a converter (Blender or the FBX SDK); keeping JSON private would remove the only raw-data export.
**What you are being asked to confirm:** Needs human research: whether `out3d.json` should be a supported format (then its joint order becomes a public contract) or stay internal.
**Related rows:** D-018 (BVH), D-006 (JSON order), D-030 (per-joint numbers stay out), D-074 (where the BVH is stored).

### D-063 · The take info panel shows camera count, frame rate, calibration error in pixels, duration and status: "show real numbers wherever the API returns them"
**What it means for a user:** You see numbers rather than badges, but the spec does not say which fps (each camera's, or the 30 fps output) or which calibration error (per camera or overall), and no colour marks a bad value [VERIFIED, `DESIGN.md:190-194, 225`].
**What it affects in the code:** A spec; the row's `DESIGN.md:192` is the metadata table, which holds. The Django `MotionVersion.fps` is the output rate `(frames - 1) / duration` (`rendering.py:93`), so that ambiguity is settled in practice as "output fps" [VERIFIED].
**If it were reversed:** Hiding numbers loses the one thing a user can act on (a camera with a much larger error moved).
**What you are being asked to confirm:** Needs human research: pick the fps and the error definition, and whether D-031's colours apply in the web app.
**Related rows:** D-030, D-031, D-009, D-074.

### D-064 · Take states are Queued, Processing, Done, Failed; after submit a linear step list (Queued → Detecting poses → Calibrating cameras → Solving 3D → Done/Failed); failures show the API's error text as-is; status refreshes every 5 seconds
**What it means for a user:** A four-step progress list rather than a bar; sync and writing have no step; the raw error text from the pipeline is what you read [VERIFIED, `DESIGN.md:113, 161-169`].
**What it affects in the code:** A spec; the FastAPI statuses are `queued`, `running`, `done`, `failed` (`api.py:200-214`), and the Django motion page polls every 2 s, not 5 (`frontend/src/features/motions/MotionPage.tsx:151-153`) [VERIFIED].
**If it were reversed:** A bar needs D-033's progress lines, which the web path does not relay.
**What you are being asked to confirm:** Needs human research: the 5 s has no reason and the built app uses 2 s (D-075); the step mapping from D-020's parsed stages is unwritten.
**Related rows:** D-020, D-033, D-075 (2 s poll), D-046 (error text as a documented message).

### D-065 · WCAG AA contrast everywhere: at least 4.5:1 for body text and 3:1 for large text; `--muted-2` (#9A9AA8) is decorative only; 12 px captions never carry essential information
**What it means for a user:** Text is readable against its background by a published standard; the lightest grey is never used for anything you must read [VERIFIED, `DESIGN.md:28, 37-40, 222`].
**What it affects in the code:** A spec; lines hold. The CSS tokens were not audited this session.
**If it were reversed:** Lower contrast looks lighter but fails users with low vision and the standard.
**What you are being asked to confirm:** WCAG 2.1 SC 1.4.3 is the right source; citation not checked, but it is the standard's well-known contrast criterion [INFERRED]. The sheet notes two corrections: 4.5:1 applies to all non-large text, not only "body text ≥16px", and white on `--purple` is about 5.2:1, not 9:1.
**Related rows:** D-066 (the other accessibility rule), D-068.

### D-066 · Every interactive element is at least 44 by 44 px; buttons at least 44 px tall
**What it means for a user:** Buttons, rows, nav links and delete icons are easy to tap on a phone [VERIFIED, `DESIGN.md:85-87, 134`].
**What it affects in the code:** A spec; lines hold.
**If it were reversed:** Smaller targets fit more on screen and fail touch users.
**What you are being asked to confirm:** WCAG 2.1 SC 2.5.5 Target Size is Level AAA (above the AA the spec names elsewhere); citation not checked. Decide whether the spec means AAA here.
**Related rows:** D-065, D-069 (mobile layout).

### D-067 · Fonts are Plus Jakarta Sans from Google Fonts with a 32/24/18/16/14/12 px scale, and JetBrains Mono for file names and error codes
**What it means for a user:** The app needs the network to load its fonts, and every page load sends a request to Google; offline it falls back to the system font [VERIFIED, `frontend/index.html:8-11`, `src/styles/tokens.css:51-52`].
**What it affects in the code:** `index.html:11` (the row's `:10`), `tokens.css:51`, `DESIGN.md:47, 58` [VERIFIED].
**If it were reversed:** Self-hosting the font files removes the dependency on Google at the cost of two files in the repo.
**What you are being asked to confirm:** Needs human research or `out of scope` (styling); the font licence (SIL OFL) is a fact about the font, not a reason for it.
**Related rows:** D-068.

### D-069 · Responsive layout: content at most 1280 px wide; project grid 4/2/1 columns at 1024/768/below; hamburger drawer at 768 px and below; page padding 64/32/16 px at 1440/768/390 px; on phones the project page stacks viewer, take list, export
**What it means for a user:** The app works on a phone with a drawer menu and a single column [VERIFIED, `DESIGN.md:125, 131-135`].
**What it affects in the code:** A spec; lines hold.
**If it were reversed:** Fixed desktop widths would break the phone use the filming session relies on.
**What you are being asked to confirm:** Needs human research or `out of scope`: breakpoints are tuned constants with no recorded reason.
**Related rows:** D-066, D-068.

### D-070 · A second backend, MotionBoxPro, on Django 5.2 with Django REST Framework under `/api/v1/` and PostgreSQL, configured from `backend/.env`; production is gunicorn running 3 uvicorn workers on a Unix socket behind nginx with certbot; `backend/requirements.txt` is a `pip freeze`
**What it means for a user:** The web app you log into is this server, not the FastAPI one; two backends exist side by side with their own storage [VERIFIED, `backend/motionboxpro/settings.py:87-89, 145-147`, `urls.py:21-25`, `README.md:13-39`].
**What it affects in the code:** `settings.py:87` (`DATABASES` from env), `urls.py:21` (the row's `:20`), `requirements.txt:9` (`Django==5.2.18`). The sheet's note that this file lacks rtmlib is out of date: `backend/requirements.txt:36` now pins `rtmlib==0.0.16` and `:24` `onnxruntime==1.31.0` [VERIFIED]. The 3 worker count is in the README [STATED, not re-checked].
**If it were reversed:** Extending FastAPI with accounts and a database was the alternative; nothing recorded compares them.
**What you are being asked to confirm:** The Django and DRF docs describe the libraries, not the reason; citation not checked. The real questions: keep both backends, and which `requirements.txt` is authoritative.
**Related rows:** D-020 (the other backend), D-052 (third storage path), D-071 to D-076 (its design).

### D-071 · Accounts: the login is the email; sessions in a cookie through DRF SessionAuthentication; every endpoint requires a login by default; CSRF is enforced on the anonymous POSTs too; password reset emails a link to `FRONTEND_URL/reset-password/<uid>/<token>` and answers the same whether or not the email exists; email goes to the console; CORS and CSRF trust only localhost:5173
**What it means for a user:** You register and log in with an email; a forgotten password gives a reset link (printed to the server console for now); the server as committed only accepts a browser on localhost, so production needs settings that are not in the repo [VERIFIED, `accounts/models.py:41` (`USERNAME_FIELD = "email"`), `settings.py:32, 145-161`, `accounts/views.py:23-31, 93-102`].
**What it affects in the code:** The row's `models.py:36` is now `:41`; `settings.py:145, 151` hold; `views.py:23` and `:93-102` (the row's `:94`) hold. `ALLOWED_HOSTS = []` at `settings.py:32` [VERIFIED].
**If it were reversed:** Token auth would suit non-browser clients; no login brings back D-056's problem.
**What you are being asked to confirm:** The Django and DRF docs support the mechanics as quoted; citation not checked. The admin site at `/cs472mbp/` (`urls.py:21`) is a security-by-obscurity choice to note.
**Related rows:** replaces D-056; D-070, D-072, D-076 (served only through the login).

### D-072 · The Django data model: every row has an owner and a public uuid; a Recording is one video; a Motion uses 2 to 4 recordings through `MotionRecording` with a `camera_slot`, slot 0 the reference; per-camera clap time, error and keypoints live on that link; a Project is a folder of motions; a Performer has no login and an optional default height; performer names unique per owner
**What it means for a user:** You upload recordings, then assemble a motion from them; the first slot is camera 0 (the sync reference and the floor's facing direction), and a new recording takes the lowest free slot, not the order you picked [VERIFIED, `motions/models.py:10-13, 153-187`, `serializers.py:164-167`, `projects/models.py:7-21, 32-49`, `recordings/models.py:10-36, 43-83`].
**What it affects in the code:** All cited lines hold. `MotionRecording.clap_time_s`, `reprojection_error_px` and `keypoints_npz` exist at `models.py:175-177` but D-074 notes they are never filled [VERIFIED for existence; filling not re-checked].
**If it were reversed:** Returning to FastAPI's take folders loses accounts, projects and versions.
**What you are being asked to confirm:** Needs human research: the slot assignment versus user order, and the integer performer ids in URLs against the uuid rule.
**Related rows:** replaces D-053 and D-054's model; D-008 and D-013 (camera 0); D-073, D-074, D-075, D-076.

### D-073 · A Django motion uses at least 2 and at most 4 recordings; the database caps `camera_slot` at 3 and the picker stops at 4
**What it means for a user:** On the web app you cannot process a fifth phone, although the pipeline and the FastAPI path accept any number [VERIFIED, `serializers.py:10-12, 137-138`, `models.py:172`, `AddRecordingDialog.tsx:11`].
**What it affects in the code:** All three places hold (the row's `AddRecordingDialog.tsx:10` is `:11`). Raising the cap needs three edits plus a migration for the validator [VERIFIED].
**If it were reversed:** Removing the cap matches D-024 at the cost of a migration and a UI change.
**What you are being asked to confirm:** Needs human research: this is D-001 back again after it was rejected; a reviewer may want `from D-024` in Lineage and a decision one way or the other.
**Related rows:** contradicts D-024 (and the rejected D-001); D-060 asks for the same 4; D-002 restated.

### D-074 · Every render is a numbered `MotionVersion` with source pipeline or manual; all outputs (`out3d`, calibration, metrics as JSON, BVH and log as text) are kept in the database and the temporary folder deleted; fps, frame count and duration are derived from `out3d`; the motion's status is its latest pipeline version's; the BVH is served at `/api/v1/motions/<uuid>/versions/<n>/bvh/`
**What it means for a user:** Every run is kept and can be compared; but the per-camera 2D joints files are thrown away, so `--resume` and any per-camera view have nothing to reuse, and each render re-detects from scratch [VERIFIED, `rendering.py:2-4, 79-93`, `models.py:64-139`, `urls.py:12-14`].
**What it affects in the code:** All cited lines hold; `fps = (frames - 1) / duration` at `rendering.py:93` [VERIFIED].
**If it were reversed:** Keeping the folder (or the `.npz` files) restores `--resume` and the D-032 view at the cost of disk.
**What you are being asked to confirm:** Needs human research: whether storing a whole take's frames in one JSON field scales, and whether deleting the keypoints is intended.
**Related rows:** D-018, D-030, D-006 (now database fields); D-023 and D-032 (lost); D-009 and D-063 (which fps).

### D-075 · A render runs the pipeline in a new spawned process once the version is committed; only one render may be queued or running on the whole server; every render recalibrates; the pose model is chosen per render; the performer height is that of the first slot whose recording has a performer with a height; the page polls every 2 s
**What it means for a user:** While anyone's render runs, everyone else gets "Another render is still running"; a crashed render left `queued` blocks every user until cleared; with two performers only the first slot's height sets the scale; an Android recording's field of view is stored but never used, so it always gets 65 degrees [VERIFIED, `rendering.py:23-30, 59-74`, `serializers.py:200-224`, `MotionPage.tsx:151-153`, `recordings/models.py:76-78`].
**What it affects in the code:** All cited lines hold (`serializers.py:213` is `:215`). `run()` is called with `recalibrate=True` and `detector=version.pose_model` and no `fov`, `smoother`, `clap_threshold` or `jobs` (`rendering.py:71-74`) [VERIFIED].
**If it were reversed:** A real queue would let renders line up per user; passing `field_of_view_deg` through is a one-line fix with a large effect for Android cameras (D-037).
**What you are being asked to confirm:** The Python docs support `spawn` only; citation not checked. The one-at-a-time check is a database read, not a lock, so two simultaneous requests can both pass.
**Related rows:** same pattern as D-020; D-037 (fov dropped), D-012 (height), D-064 (5 s versus 2 s), D-072.

### D-076 · Recordings are uploaded one video at a time and stored under `MEDIA_ROOT/<model>/<uuid>/<file>`; any file OpenCV can open is accepted (picker asks for `video/*`), no size limit; width, height, fps and duration read with OpenCV; a JPEG thumbnail 1 second in; videos and thumbnails served only through the logged-in API
**What it means for a user:** You can upload any video, including a re-encoded one, which D-038 says will mis-calibrate; the list shows thumbnails without loading videos; nothing stops a 10 GB upload [VERIFIED, `utils/files.py:1-6`, `recordings/video.py:8-41`, `recordings/views.py:36-44`, `RecordingsPage.tsx:55`].
**What it affects in the code:** All cited lines hold (`views.py:35` is `:36`). The fps and frame count are OpenCV's container estimates, so `duration_s` can be off (as D-033 notes) [VERIFIED].
**If it were reversed:** Refusing non-`.mov`/`.mp4` files and adding a size limit matches the FastAPI path and D-038 at the cost of two checks.
**What you are being asked to confirm:** Needs human research: settle the file rule across D-038, D-054, D-060 and this row, and add a size limit or decide not to.
**Related rows:** D-038, D-054, D-060 (file rules), D-040 (height restated in `Performer.height_m`, four copies), D-071 (served behind login), D-072.

---

## Group 8: Project process (CI, docs, bots)

### D-058 · Before a pull request that touches `backend/` or `desktop/`: run the whole pytest suite including the Node-driven desktop tests (skipped, not failed, when Node or `desktop/node_modules` is missing), plus `npm test` and `npm run typecheck`; for a stage change also run one real take through the tester and put its glance numbers before and after in the PR
**What it means for a user:** Changes to the pipeline are supposed to arrive with real-take numbers; but nothing enforces it, and a green suite may have skipped the desktop tests [VERIFIED, `docs/procedures/testing-the-backend.md:12-33`, `backend/tests/conftest.py:11-12`].
**What it affects in the code:** The desktop marker at `conftest.py:11` (the row's `:9`); the procedure lines hold (`:33`) [VERIFIED]. No CI workflow was checked for this.
**If it were reversed:** A CI job that fails when the desktop tests skip would enforce half of it; the real-take half cannot be automated without footage in CI.
**What you are being asked to confirm:** Needs human research or `out of scope` (development practice); decide whether skipped-means-fail in CI.
**Related rows:** D-033 and D-049 (what the desktop tests guard), D-039 and D-051 (other paper procedures).

### D-059 · Windows is a documented setup for Windows PowerShell 5.1 under the default Restricted policy: call `.venv\Scripts\python.exe` directly, type `npm.cmd`, one command per line, pass a take's videos through `Get-ChildItem ... | Sort-Object Name`; changing the policy is optional
**What it means for a user:** A Windows teammate can run everything without changing system settings, at the cost of longer commands; camera order still comes from file names [VERIFIED, `docs/procedures/windows-setup.md:14-16, 36-42`].
**What it affects in the code:** A procedure; lines hold [VERIFIED]. Nothing in code enforces it.
**If it were reversed:** Asking users to run `Set-ExecutionPolicy` once gives shorter commands but a system-wide change some will refuse.
**What you are being asked to confirm:** Microsoft's about_Execution_Policies supports the constraint (Restricted is the client default), not the choice to work around it; citation not checked. May be `out of scope` as setup instructions.
**Related rows:** D-058 (the test commands it translates), D-057 (Windows cancel path).

### D-068 · `docs/DESIGN.md` is the single source of truth for visual design, superseding the screens PDF; a closed colour palette and one spacing scale (4/8/12/16/24/32/48/64 px) with "no arbitrary pixel values"
**What it means for a user:** Frontend changes are checked against one document; the document itself breaks its scale in places (badge padding 10 px, badge font 13 px, nav height 56 px) [VERIFIED, `DESIGN.md:4-5, 71-73, 221`; the breaks are [STATED] from the sheet].
**What it affects in the code:** A procedure; the row's `DESIGN.md:12`, `:66`, `:231` map to the palette and spacing sections and the "Don't" list (`:221`), which hold. The CSS tokens were not audited.
**If it were reversed:** Without a single source, the PDF and the code drift apart again.
**What you are being asked to confirm:** Needs human research or `out of scope` (frontend process); fix or allow the three exceptions.
**Related rows:** D-065, D-066, D-067, D-069 (the rules it contains); D-060 to D-064 (the screens it specifies).

---

## Rows whose "Where" no longer matches the code

Checked against commit 1209a02. The sweep merged on 2026-10-27/28 (`cleanup/dead-code-backend`, including 7397631 of 2026-10-22, "remove unused calibration loop constants") removed `CALIB_CONVERGENCE_PX` and `CALIB_MAX_ITERATIONS` from `config.py` (they were at seed lines 55-56) and the docs sweep renamed `docs/backend_outline_functions.md` to `docs/backend-outline.md` [VERIFIED by `git log -S` and file listing]. No row cites either constant by name and no row cites the renamed document, so the effect is line drift, not broken references. Rows are listed by how far they have moved.

Stale enough to mislead (file shorter than the cited line, constant moved to another section, or the cited file no longer holds the behaviour):
- D-031: `desktop/src/renderer/main.ts:226` no longer holds the thresholds; they are in `desktop/src/shared/metrics.ts:103-107`. README line is `:103`, procedure lines are `:66-69`.
- D-055: `frontend/src/features/projects/ProjectDetailPage.tsx:131` (file is 66 lines, no clips code) and `StudioProvider.tsx:33` (seed recordings only). The `clips` code survives only in `src/lib/clips.ts` and `supabase/clips.sql`, unrouted.
- D-024: "Where" says "pending"; the change was made (`config.py:22`, `run_pipeline.py:393`, `api.py:71, 456`).
- D-047: every cited line (`run_pipeline.py:186, 204, 627, 684`) has moved; the machinery is at `:212-325`. Superseded anyway.
- D-007 and D-022: `backends.py:159`, `:149`, `:177`, `:180` moved to `:236`, `:177`, `:189`, `:275` after PR #110 added mode, device and tracking options; D-022's "mode not exposed" is no longer true.
- D-023: `run_pipeline.py:189, 201` are now `:508-525`; the fingerprint also carries `detector_settings` now.
- D-052: `.env.example:3` is now `:5-6`, and the file's header says no routed page reads these variables.
- D-054: `frontend/src/lib/api.ts:102` (file is 100 lines; upload at `:84-91`).
- D-070: reviewer note that `backend/requirements.txt` lacks rtmlib is out of date (`:36` pins it).

Moved by more than about 30 lines within the same file (behaviour unchanged):
- D-002 (`config.py:14, 88` → `:22, :135`), D-009 (`config.py:19` → `:44`), D-010 (`config.py:36` → `:95-115`), D-012 (`config.py:69` → `:121-122`), D-013 (`config.py:79` → `:129`), D-014 (`config.py:41, 86` → `:101, :133`), D-015 (`config.py:43, 92, 65` → `:103, :140, :115`), D-016 (`config.py:90` → `:137`), D-017 (`config.py:95` → `:143-144`), D-035 (`config.py:82` → `:127`), D-037 (`config.py:62` → `:107`), D-042 (`config.py:109` → `:155-156`), D-043 (`config.py:104` → `:150`; `run_pipeline.py:177` → `:358`), D-045 (`config.py:32, 35` → `:55, :58`), D-026 (`config.py:113` → `:170`), D-027 (`config.py:116, 121` → `:173-178`): all because the chirp and RTMPose option blocks were inserted above them in `config.py`.
- D-008 (`sync.py:69, 142` → `:96, :168`), D-046 (`sync.py:139` → `:143-151`; `run_pipeline.py:386, 271` → `:359, :414`), D-020 (`api.py:52, 66, 188` → `:229, :118, :164`), D-032 (`api.py:582, 601, 622, 551` → `:607, :628, :640, :558`), D-030 (`api.py:559` → `:565`; `metrics.py:116` → `:104`), D-048 (`run_pipeline.py:183, 329` → `:212, :360`), D-049 (`run_pipeline.py:242, 480, 493` → `:252, :540-563`), D-025 (`backend/mocap_pipeline/README.md:106` → `:134`), D-018 (`joints.py:60` → `:31-89`), D-051 (`desktop-tester.md:61` → `:67`).

Moved by a few lines only (still findable): D-003, D-004, D-005, D-006, D-021, D-033, D-040, D-041, D-044, D-053, D-056, D-057, D-058, D-064, D-067, D-071, D-073, D-075, D-076.

Still exact: D-011, D-019, D-028, D-029, D-034, D-036, D-038, D-039, D-050, D-059, D-060, D-061, D-062, D-063, D-065, D-066, D-068, D-069, D-072, D-074. D-001 is rejected and its cited lines now hold the minimum, not a maximum.

Not yet explained: none. All 76 rows have a section.
