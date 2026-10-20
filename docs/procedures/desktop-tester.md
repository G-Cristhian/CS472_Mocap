# Testing the backend with the desktop app

For anyone who wants to run the pipeline on a take without the terminal or the web app, and see the result at once. The app lives in `desktop/`; it runs the same command the terminal procedures use and leaves the same files behind, so a take processed here is processed exactly as in [processing-a-take.md](processing-a-take.md).[^1]

Before step 1: Node is installed (the frontend needs it too), the backend works ([mac-setup.md](mac-setup.md), through step 3; on Windows the virtual environment must be at `backend\.venv`, where the app looks for it[^3]), and the take's videos are in one folder, originals, named with the camera number first ([filming.md](filming.md), section 8).

## 1. Install and start

Every command here runs in the app's folder, `desktop` inside your copy of the repository. A new terminal does not open there: PowerShell opens in your home folder, or wherever it was started from, such as your Windows Desktop folder, and npm run anywhere else stops with `Could not read package.json`.[^23] `cd desktop` on its own means the app's folder only when you are already in the repository; from your home folder it fails or opens the Windows Desktop. So go to the folder by its full path first. The paths below assume you cloned the repository into your home folder; if it is somewhere else, use that path.

| | Mac (Terminal) | Windows (PowerShell) |
|---|---|---|
| Go to the app's folder | `cd ~/CS472_Mocap/desktop` | `cd $HOME\CS472_Mocap\desktop` |
| Install, once per machine | `npm install` | `npm.cmd install` |
| Start, every time | `npm start` | `npm.cmd start` |

Type each command on its own line and press Enter. Windows PowerShell does not accept `&&` between commands, so a line copied from a Mac page that joins commands with `&&` fails there.[^24] On Windows, type `npm.cmd` wherever a page says `npm`: PowerShell blocks `npm` itself until scripts are allowed, and `npm.cmd` is the same program without that block.[^25] In Command Prompt or Git Bash, plain `npm` works.

The first install downloads Electron, about 110 MB, which takes about 270 MB once unpacked.[^2] npm may end with `npm warn allow-scripts` naming electron and esbuild; the install still ran their setup, so the warning can be ignored.[^26] `npm start` builds the app and opens the window. It finds Python on its own: the backend's virtual environment if `backend/.venv` exists, otherwise whatever `python3` (or `python` on Windows) is on the PATH.[^3]

If the window does not open, the terminal says why:

| What the terminal says | Why | What to do |
|---|---|---|
| `Could not read package.json` (`ENOENT`) | the terminal is not in the app's folder | run the "go to the app's folder" command above, then try again |
| `npm.ps1 cannot be loaded because running scripts is disabled on this system` | PowerShell blocks scripts by default | type `npm.cmd` instead of `npm` |
| `The token '&&' is not a valid statement separator in this version` | a line copied from a Mac page | run each part on its own line |
| `Cannot find path '...\CS472_Mocap\desktop'` | the repository is not in your home folder | use the path of the folder you cloned into |

## 2. Pick the take

1. **Choose folder…** and pick the take's folder. Every `.mov` and `.mp4` in it is listed, sorted by name with numbers in natural order, so `cam2` comes before `cam10`.[^4] The list order is the camera order the pipeline gets, camera 0 first; the arrows move a file up or down, the tick leaves it out.
2. At least two videos must be ticked.[^5]
3. **Check the videos** before a long run. It runs the pre-flight check from [filming.md](filming.md) section 9 on the ticked files, in seconds, without the pose model: resolution, frame rate, length, lens metadata and the clap time of each file, then the cross-camera warnings (frame rates or lengths that differ) and the verdict.[^17] A file whose clap it cannot find says what the sharpest sound measured; lower the clap threshold (step 8) and check again, or give the clap times by hand (step 9).
4. **Performer height** in metres, from the take log; the app accepts 1 to 2.5.[^6] It is only used while calibrating: with Recalibrate off and a `calibration.json` already in the output folder, the height is ignored, and the app says so under the box.[^18]
5. **Detector**: MediaPipe unless you are comparing models ([comparing-pose-models.md](comparing-pose-models.md)).
6. **Smoother**: Savitzky-Golay unless you are comparing filters. Butterworth is the other; after a run, **Rerun with the other smoother** in the result panel does the comparison for you (section 4).
7. **Field of view**: only used for cameras without iPhone lens metadata; 65 is the pipeline's default, the Fold is about 75.[^7]
8. **Clap loudness threshold**: 1 is the pipeline's normal setting. 0.5 accepts a clap half as strong against the room, for a faint clap or a noisy venue; it is the `--clap-threshold` option.[^19]
9. **Clap times**: blank, and the pipeline finds the clap in each file's audio. When the search locks onto the wrong sound, type one time per video in seconds, camera 0 first, read off a video player; the app refuses a list of the wrong length. It is the `--sync` option.[^19]
10. **Videos detected at once**: 0 lets the pipeline pick (one process per video, up to 4 and the number of processor cores); 1 detects the videos one after another, for a laptop that struggles. It is the `--jobs` option.[^20]
11. **Output folder**: defaults to `backend/output/<folder name>-<date and time>`, one folder per take.[^8] Change it to reprocess into a folder you already have.
12. **Recalibrate** is on by default so a stale `calibration.json` in the output folder is never reused by accident; **Resume** reuses the stage files already in that folder, which turns a rerun into seconds.[^9]

## 3. Run

Press **Run the pipeline**. The bar follows detection frame by frame, then jumps through sync, calibration, triangulation and writing.[^10] Detection is three quarters of the bar because it is nearly all of the wall time.[^11] Under the bar, one line per video says where it is: waiting, detecting (with the frame), done (with the seconds it took), reused (saved joints from an earlier run) or failed, with the reason. The videos are detected several at a time, so the lines move independently; a video that fails does not stop the others, and the run ends after detection with a message naming every failed file.[^21] The log is everything the pipeline printed, the same lines a terminal run shows.

**Cancel** stops the Python process; a cancelled run leaves whatever stage files it had finished, which Resume can pick up.[^12]

## 4. Read the result

The skeleton plays as soon as the run finishes. Drag to rotate, wheel to zoom, the slider scrubs, Play/Pause toggles. The figure is the BVH the pipeline wrote, in metres on a one-metre grid.[^13]

Under the viewer, the numbers from `out3d.metrics.json`, stage by stage, so a poor take can be traced to its cause.[^22] **At a glance** has the ones the processing guide asks for, coloured by its thresholds:[^14]

| Number | Green | Red |
|---|---|---|
| Calibration error, worst camera | under 3 px | over 10 px |
| Triangulation error, mean | under 3 px | over 10 px |
| Bone length spread | under 10 mm | over 20 mm |
| Joints missing | under 5 % | over 15 % |
| Upright frames for height | 30 or more | under 10 |

Then, per stage: how well each camera saw the performer (frames with nobody detected, mean confidence, seconds taken); the clap times and where they came from; each camera's calibration error and whether an old calibration was reused (in which case the height was not applied); the triangulation error with the worst joints and the joints most often missing; what smoothing did (jitter before and after, gaps filled, gaps left); and the least rigid bones. Reading the error backwards like this answers "which camera, which joint, which stage" from one run.

**Rerun with the other smoother** runs the take again with Resume on and the smoother switched: the joints, clap times, calibration and 3D points are reused, only the smoothing and the skeleton are redone, so it takes seconds. The **Runs of this take** table then shows the two runs side by side (jitter before and after smoothing, bone spread, calibration error, missing joints, time); lower jitter with the same bone spread is the better filter for that take ("Choosing the smoother" in `backend/mocap_pipeline/README.md`). The table lasts while the app is open and starts afresh for a new output folder.

Write the glance numbers in the session log with a word on how the take looked. **Open the output folder** shows every file the run produced; **Run another take** goes back to section 2 with the same folder listed.

## When it fails

The result panel shows the pipeline's own message and opens the log. The messages and what to do about them are the table in [filming.md](filming.md), section 11; they are the same whether the run came from the app or the terminal.[^15] If the app says it could not start Python, the backend is not set up on this machine: [mac-setup.md](mac-setup.md). On Windows, check that `backend\.venv\Scripts\python.exe` exists.

## Working on the app

`npm run preview` in `desktop/` serves the page at http://localhost:5174 in a browser with a mocked pipeline that replays a real run's printed lines, for changing the page without Electron.[^16] `npm test` runs the progress parser, the check-output parser and the metrics panel against those lines and a sample `metrics.json`. `npm run typecheck` checks both the page and the Electron side.

---
## Sources

[^1]: `desktop/src/main/pipeline.ts`, `pipelineArgs`: the command is `python -u -m mocap_pipeline.run_pipeline <videos> --height-m … --out <folder>/out3d.json --calibration <folder>/calibration.json --detector … --smoother … --fov … --jobs …`, plus `--clap-threshold`, `--sync`, `--recalibrate` and `--resume` when set, run from `backend/`, the same as [processing-a-take.md](processing-a-take.md) step 3.
[^2]: The `electron` package's postinstall downloads the runtime for the platform (https://www.electronjs.org/docs/latest/tutorial/installation). Measured on 2026-10-20 for Electron 33.4.11 on Windows x64: the download, kept in Electron's cache as `electron-v33.4.11-win32-x64.zip`, is 110 MB, and the unpacked `desktop/node_modules/electron/dist` is 269 MB.
[^3]: `desktop/src/main/pipeline.ts`, `resolvePython`: tries `backend/.venv/Scripts/python.exe` then `backend/.venv/bin/python`, then falls back to the PATH.
[^4]: `desktop/src/main/main.ts`, the `list-videos` handler sorts with `localeCompare(…, { numeric: true })`. The naming rule is filming.md section 8.
[^5]: `MIN_CAMERAS = 2` in `backend/mocap_pipeline/config.py`; two views are the minimum for triangulation (D-002 on `docs/decisions/DECISIONS.md`). The app refuses to run with fewer (`desktop/src/renderer/main.ts`, `readOptions`).
[^6]: The same limits as the API's upload check, `MIN_HEIGHT_M, MAX_HEIGHT_M = 1.0, 2.5` in `backend/api.py`.
[^7]: `DEFAULT_HFOV_DEG = 65` in `config.py`; iPhone focal lengths come from the file's metadata (`stage2_reconstruct/iphone_camera.py`). The Fold estimate is filming.md section 3.
[^8]: `desktop/src/main/main.ts`, the `default-out-dir` handler. One folder per take is processing-a-take.md step 1, so takes never share a calibration.
[^9]: The pipeline reuses an existing `--calibration` file unless `--recalibrate` is given, and `--resume` reuses saved stage files whose inputs have not changed (`backend/mocap_pipeline/README.md`, "Rerunning and debugging"; D-023 for the detector check).
[^10]: `backend/mocap_pipeline/stage1_keypoints/detect.py` prints `progress: detect <video> <i>/<n>` every 30 frames when the `MOCAP_PROGRESS` environment variable is set; the app sets it (`pipeline.ts`). The later stages are recognised from the lines `run_pipeline.py` already prints (`desktop/src/shared/progress.ts`).
[^11]: `WEIGHTS` in `desktop/src/shared/progress.ts`: detection 0.75, sync 0.05, calibration 0.08, triangulation 0.05, writing 0.07. Team judgement from the README's "full run, minutes; `--resume` run, seconds"; no timing measurement yet. The `timing` block in `metrics.json` will give the real split once a few takes have run.
[^12]: `desktop/src/main/pipeline.ts`, `cancel()` sends the process a kill signal. Stage files are written as each stage finishes (`run_pipeline.py`), so a cancelled run keeps the stages before the one it was in.
[^13]: The BVH is written in centimetres, Y up (`stage3_rig/bvh_writer.py`, D-018); the viewer scales any skeleton whose bone offsets exceed five units by 0.01 (`desktop/src/renderer/viewer.ts`).
[^14]: The thresholds are processing-a-take.md step 4, with their own sources there: the synthetic benchmark for the pixel error, Karashchuk et al. 2021 (DOI 10.1016/j.celrep.2021.109730) for limb-length variability, `tests/test_metrics.py` for the missing fraction, `MIN_UPRIGHT_FRAMES` for the upright count. The red limits are the pipeline's own give-up points (`CALIB_MAX_ERROR_PX = 10`, `MIN_UPRIGHT_FRAMES = 10`) or team judgement (20 mm, 15 %).
[^15]: The app shows the last line the pipeline wrote to stderr, which is the `SystemExit` message `run_pipeline.py` raises with the text in that table (`desktop/src/shared/progress.ts`, `result()`).
[^16]: `desktop/vite.config.ts` and `desktop/src/renderer/mock.ts`; the sample skeleton is `frontend/public/samples/sample_take.bvh`.
[^17]: `desktop/src/main/pipeline.ts`, `runCheck`, runs `python -u -m mocap_pipeline.check_videos <videos> [--clap-threshold …]`; `desktop/src/shared/check.ts` reads what it prints. The check itself is `backend/mocap_pipeline/check_videos.py`, filming.md section 9.
[^18]: The pipeline only reads `--height-m` inside calibration (`scale_floor.py`, called from `run_pipeline.py` when a calibration is computed); an existing `--calibration` file is loaded as is. The app shows the note whenever Recalibrate is unticked (`desktop/src/renderer/main.ts`, `updateHeightNote`), and the result panel's calibration section says "reused" when it happened (`metrics.json`, `calibrate.reused_file`).
[^19]: `--clap-threshold` multiplies `CLAP_MIN_PROMINENCE` and `CLAP_MIN_RISE` in `config.py` (D-045, D-046 on `docs/decisions/DECISIONS.md`); `--sync` takes one clap time per video and skips the audio search (`stage2_reconstruct/sync.py`, `synchronise`).
[^20]: `--jobs` and `detect_jobs` in `run_pipeline.py`; `DETECT_JOBS = 0` and `DETECT_MAX_AUTO_JOBS = 4` in `config.py` (each process loads its own copy of the pose model).
[^21]: `run_pipeline.py`, `_detect_videos`: every video is attempted, each failure is printed as `Detection failed for <file>: <reason>`, and the run stops with a summary naming the failed files; the joints of the others are saved for `--resume`. The per-video lines in the app come from `desktop/src/shared/progress.ts`.
[^22]: `desktop/src/shared/metrics.ts`, `metricSections`, reads the keys `metrics.py` and the stages record: `stage1.<camera>`, `sync`, `calibrate`, `scale`, `triangulate`, `pose_raw`, `pose_final`, `smooth`, `rig.bone_lengths`, `timing`. The thresholds for the triangulation error are the same as for the calibration error (both are mean reprojection errors in pixels); the jitter colour is team judgement (over 40 % less is green, under 10 % red).
[^23]: Checked on 2026-10-20 on Windows 11: a new Windows PowerShell window starts in the home folder, `C:\Users\<name>`. The Windows Desktop folder is `C:\Users\<name>\Desktop`, or `C:\Users\<name>\OneDrive\Desktop` when OneDrive backs it up. Run from the OneDrive desktop folder, `npm install` stopped with `npm error enoent Could not read package.json`. On that machine `cd desktop` from the home folder failed, because the Desktop is under OneDrive; without OneDrive it opens `C:\Users\<name>\Desktop`. Neither is the app.
[^24]: Windows PowerShell 5.1, the version built into Windows, rejects `&&` with "The token '&&' is not a valid statement separator in this version". PowerShell 7 added it (Microsoft Learn, about_Pipeline_Chain_Operators). Checked on 2026-10-20.
[^25]: Node's Windows installer puts `npm.ps1` and `npm.cmd` side by side in `C:\Program Files\nodejs`, and PowerShell runs `npm.ps1`. The default execution policy on Windows client editions, Restricted, refuses `.ps1` files (Microsoft Learn, about_Execution_Policies); `npm.cmd` is a batch file, which the policy does not cover. Checked on 2026-10-20 in a PowerShell session with the Restricted policy: `npm --version` failed with the npm.ps1 error and `npm.cmd --version` printed the version. Running `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once also makes plain `npm` work.
[^26]: Checked on 2026-10-20 with npm 11.17.0: `npm.cmd install` in an empty folder holding only the app's `package.json` and `package-lock.json` printed "2 packages have install scripts not yet covered by allowScripts" for electron and esbuild, and still unpacked Electron (`node_modules/electron/dist/electron.exe` present, `electron --version` printed v33.4.11). If a later npm stops running them, the warning itself names the fix: `npm approve-scripts <pkg>`.
