# Target frame rate as an option, with time-based constants

Status: draft for team review. Not implemented.
Replaces the open question on D-009 (shared 30 fps clock).

## 1. The problem

Every camera is resampled onto one shared clock after the clap sync
(`stage2_reconstruct/sync.py`). That clock is `config.TARGET_FPS = 30.0`, a
value from the pipeline skeleton (d85ec2c, 2026-09-30) with no source. The
filming protocol asks phones for 60 or 120 fps, so three of every four
detections at 120 are blended away before triangulation, and the 60-versus-120
comparison planned in `docs/procedures/filming.md` section 6 cannot be
measured in the output.

Three downstream constants are counted in frames of that clock, so they
silently change meaning if the clock changes (section 5).

## 2. The option

One new setting, `target_fps`, with the value `auto` or a number.

| Value | Meaning |
|---|---|
| `auto` (default) | the slowest camera's measured rate: the shared clock never runs faster than the slowest source |
| a number, e.g. `60` | that rate, if no camera is slower than it |

Rules:

- **Auto measures, it does not trust the container.** Each camera's rate is the
  median frame interval of its stage 1 timestamps (`Keypoints2D.timestamps`),
  not the nominal `fps` field, which the container can misreport and which
  does not see a mid-take rate change. The nominal value is kept in metrics
  for comparison.
- **Never above the slowest camera.** A requested rate above the slowest
  camera's measured rate would make the resampler invent frames (every output
  frame an interpolation of two source frames, none of them real). Proposed:
  clamp to the slowest rate, print a warning, and record both the requested
  and the used rate in metrics. Open question 1 asks whether to reject instead.
- **Presets in the user interfaces:** auto, 24, 30, 60, 120, plus a free
  number. Section 3 covers 24.
- **No lower bound beyond sanity** (at least 1 fps). Going below the slowest
  camera is the current behaviour (60 to 30) and stays allowed.

What the user sees: the BVH `Frame Time` and `out3d.json` `fps` carry the
chosen rate. `metrics.json` records `sync.target_fps_requested`,
`sync.slowest_camera_fps` (measured), `sync.nominal_fps` per camera and
`sync.common_fps` (used).

## 3. Should 24 be offered?

Yes, as a preset, because it is free to add and it is the delivery rate most
animation tools default to (Blender, Maya, Unreal sequencer all open at 24).
Two caveats to write into the preset's tooltip:

- 24 does not divide 60 or 120, so every output frame is a blend of two
  source frames (the 60/24 ratio is 2.5). At 30 from 60 every other output
  frame is an exact source frame. Linear blending of 2D joints slightly
  softens the fastest moments, so 24 is a delivery choice, not a measurement
  choice.
- Time constants round to fewer frames at 24 (section 5): the smoothing
  window becomes 5 frames, not 7.

For the frame rate experiment (set B at 60 against set C at 120) use auto, so
each take is reconstructed at its own native rate.

## 4. Where the option threads through

Today height, field of view and detector choice already take this path.
`target_fps` follows it exactly.

| Layer | File | Change |
|---|---|---|
| config | `backend/mocap_pipeline/config.py` | `TARGET_FPS = 30.0` becomes `DEFAULT_TARGET_FPS = None` (None means auto) |
| sync | `stage2_reconstruct/sync.py` | `synchronise(..., target_fps=None)`; measures the slowest rate, applies the clamp, builds the common timeline from the chosen rate |
| pipeline | `run_pipeline.py` | `run(..., target_fps=None)` passes it to sync; `--target-fps auto|N` on the command line, default auto; metrics as in section 2 |
| constants | `scale_floor.py`, `smooth.py` | read frame counts from `config.frames(seconds, pose.fps, ...)` (section 5) instead of the fixed constants |
| API | `backend/api.py` | optional form field `target_fps` ("auto" or a number 1 to 240), validated in `check_upload`, stored on the take record, passed through `submit` and `run_take` |
| desktop tester | `desktop/src/main/pipeline.ts`, `desktop/src/renderer/index.html` | `RunOptions.targetFps`; a select with the presets and a custom box; `pipelineArgs` adds `--target-fps` |
| web frontend | `frontend/` upload form | the same select, sent as the form field |
| resume | `io.stage_paths` | a saved sync file is only reused if it was made at the same target rate (as detector choice is handled today) |

The calibration file is geometry in pixels and is independent of the rate, so
an existing `calibration.json` stays valid.

## 5. Constants that must move from frames to seconds

Each is a duration in disguise. Expressed in seconds and converted at the
chosen rate they keep their meaning at any clock.

| Today | Value | Meaning | Proposed | Conversion |
|---|---|---|---|---|
| `MIN_UPRIGHT_FRAMES` | 10 | frames standing upright needed to measure height | `MIN_UPRIGHT_S = 0.33` | `ceil(s * fps)`, min 2 |
| `MAX_GAP_FILL_FRAMES` | 10 | longest run of missing joint frames that is interpolated | `MAX_GAP_FILL_S = 0.33` | `round(s * fps)`, min 1 |
| `SMOOTH_WINDOW_FRAMES` | 7 | Savitzky-Golay window | `SMOOTH_WINDOW_S = 0.23` | `round(s * fps)` made odd, min `SMOOTH_POLYORDER + 2` |

Resulting frame counts:

| Rate | upright | gap fill | smoothing window |
|---|---|---|---|
| 24 | 8 | 8 | 5 |
| 30 | 10 | 10 | 7 |
| 60 | 20 | 20 | 15 |
| 120 | 40 | 40 | 27 |

At 30 the counts are exactly today's values, so existing behaviour and tests
are unchanged by the conversion alone.

Not converted:

- `SYNC_MAX_INTERP_GAP_FRAMES = 2.5` is already in the camera's own frames
  (`sync._resample` divides by `kp.fps`) and so is robust as it stands. It
  describes "one dropped frame is fine, a stall is a gap", which is a
  statement about frames, not time.
- `SMOOTH_POLYORDER = 2` is dimensionless.
- The clap constants are already in seconds.

One helper carries the conversion so no stage repeats it:

```python
def frames(seconds: float, fps: float, *, odd: bool = False, minimum: int = 1) -> int:
    n = max(minimum, int(round(seconds * fps)))
    if odd and n % 2 == 0:
        n += 1
    return n
```

Seconds is the right unit for all three. The smoothing window could instead
be given as a cutoff frequency, but a Savitzky-Golay filter has no clean
cutoff (its response depends on window and order together), so a window
length in seconds is the honest parameter. The 3 second hold in the filming
guide and the "30 upright frames" check in D-031 are the same duration logic
and should read 1 second once this lands.

## 6. Where the current numbers came from

None of them is D-009. D-009 covers only the 30 fps clock.

| Constant | Introduced | On the sheet | Source |
|---|---|---|---|
| `TARGET_FPS = 30` | Giancarlo, d85ec2c, 2026-09-30 | D-009, needs human research | none |
| `MIN_UPRIGHT_FRAMES = 10` | Jeremiah, dd16683, 2026-10-04 | D-035 (with the 3 s hold), needs human research | team judgement: "a third of a second at 30 fps" |
| `MAX_GAP_FILL_FRAMES = 10` | placeholder in d85ec2c, value from Jeremiah's `multicam_3d` config in dd16683 | no row | none |
| `SMOOTH_WINDOW_FRAMES = 7`, `SMOOTH_POLYORDER = 2` | Jeremiah, dd16683; window reduced for punches 2026-10-13 | D-017, cited, pending review | the filter is Savitzky and Golay 1964; the window and order are team judgement |
| `SYNC_MAX_INTERP_GAP_FRAMES = 2.5` | Jeremiah, dd16683 | no row | none |

The equations they feed are standard: straight-line interpolation
(`numpy.interp`) for resampling and gap filling, and the Savitzky-Golay
least-squares polynomial filter (`scipy.signal.savgol_filter`) for smoothing.
The upright test (hips and shoulders within 5 percent of the heel-to-ear
line) is a team heuristic with no source.

Merging this proposal is itself a decision: the conversion to seconds amends
D-017 and D-035, closes D-009, and gives `MAX_GAP_FILL` and
`SYNC_MAX_INTERP_GAP` their first rows. The design-decisions workflow will
pick these up on the merge; the rows should cite this document.

## 7. Cost

Stage 1 (the detector) reads every source frame whatever the target, so the
dominant cost does not change. Sync, calibration, triangulation, gap filling,
smoothing and the BVH writer are linear in shared frames: at 60 they do
twice the work of today, at 120 four times, all of it seconds against the
detector's minutes. `out3d.json` and the BVH grow in proportion. The run log
in `metrics.json` already times each stage, so the first real take at 60 and
120 gives the measurement.

## 8. Tests

- `synthetic_scene.py` and the synthetic pipeline tests build their timeline
  from `config.TARGET_FPS`; they take the scene's rate instead.
- New: auto picks the slowest camera (60/30/30 scene gives 30; 120/60 gives
  60); an explicit 60 on a 60/120 scene gives 60; an explicit 120 on a 60/120
  scene clamps to 60 with the warning recorded; the three constants scale
  (table in section 5); BVH `Frame Time` equals `1 / fps`; the API rejects
  `target_fps=0` and `target_fps=abc` with 422 and accepts `auto`;
  `pipelineArgs` emits `--target-fps`.

## 9. Open questions for the team

1. Above the slowest camera: clamp with a warning (proposed) or refuse the
   run? Refusing is stricter and protects the experiment; clamping never
   blocks a user.
2. Should auto snap to the nearest standard rate (24, 25, 30, 50, 60, 120) or
   use the measured value as is (for example 59.94)? Proposed: as is, since a
   measured 59.94 is the truth and the BVH carries any frame time.
3. Is 24 in the preset list, given section 3?
4. Does D-031's "30 upright frames" become "1 second" in the result check?
