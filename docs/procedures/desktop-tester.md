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

1. **Choose folder…** and pick the take's folder. Every `.mov` and `.mp4` in it is listed, sorted by name with numbers in natural order, so `cam2` comes before `cam10`.[^4] The list order is the camera order the pipeline gets, camera 0 first; the arrows move a file up or down, the tick leaves it out. Choosing the same folder again refreshes the list and keeps the ticks, the order and the output folder (a file copied in since takes its place in name order, or goes last, with a note, if you reordered the list by hand); a folder that cannot be read, or holds no videos, leaves the take as it was and says so next to the folder name.
2. At least two videos must be ticked.[^5]
3. **Check the videos** before a long run. It runs the pre-flight check from [filming.md](filming.md) section 9 on the ticked files, in seconds, without the pose model: resolution, frame rate, length, lens metadata and the clap time of each file, then the cross-camera warnings (frame rates or lengths that differ) and the verdict.[^17] A file whose clap it cannot find says what the sharpest sound measured; lower the clap threshold (step 8) and check again, or give the clap times by hand (step 9).
4. **Performer height** in metres, from the take log; the app accepts 1 to 2.5.[^6] It is only used while calibrating: with Recalibrate off and a `calibration.json` already in the output folder, the height is ignored, and the app says so under the box.[^18]
5. **Detector**: MediaPipe unless you are comparing models ([comparing-pose-models.md](comparing-pose-models.md)). With RTMPose, two more boxes appear: **RTMPose mode** (lightweight, balanced or performance; balanced is the pipeline's default) and **RTMPose person detector every N frames** (1 runs it on every frame; 5 runs it on one frame in five and follows the performer from their joints in between). They are `--rtmpose-mode` and `--rtmpose-detect-every`.[^27]
6. **Smoother**: Savitzky-Golay unless you are comparing filters. Butterworth is the other; after a run, **Rerun with the other smoother** in the result panel does the comparison for you (section 4).
7. **Field of view**: only used for cameras without iPhone lens metadata; 65 is the pipeline's default, the Fold is about 75.[^7]
8. **Clap loudness threshold**: 1 is the pipeline's normal setting. 0.5 accepts a clap half as strong against the room, for a faint clap or a noisy venue; it is the `--clap-threshold` option.[^19]
9. **Clap times**: blank, and the pipeline finds the clap in each file's audio. When the search locks onto the wrong sound, type one time per video in seconds, camera 0 first, read off a video player, with a point for decimals (1.25); the app refuses a list of the wrong length. The times go to the videos by position, so changing the ticks or the order afterwards empties the box and says so: type them again in the new order. It is the `--sync` option.[^19]
10. **Videos detected at once**: 0 lets the pipeline pick (one process per video, up to 4 and the number of processor cores); 1 detects the videos one after another, for a laptop that struggles. It is the `--jobs` option.[^20]
11. **Output folder**: defaults to `backend/output/<folder name>-<date and time>`, one folder per take.[^8] Change it to reprocess into a folder you already have: type the path, or press **Choose folder…** next to it, which opens at the current path and can make a new folder.
12. **Recalibrate** is on by default so a stale `calibration.json` in the output folder is never reused by accident; **Resume** reuses the stage files already in that folder, which turns a rerun into seconds.[^9]

## 3. Run, or queue a comparison

Press **Run the pipeline**. The run goes into the **Queue** panel and starts. While it runs, the form stays open and the button reads **Add to queue**: change the take or the settings and press it again, and that run waits its turn. Runs go one after another, never two at once, because one run already keeps every processor core busy.[^28] Each run in the queue shows its take, its settings and, when done, its time or the first line of its failure; **×** takes a waiting run off, **Clear finished** tidies the list. A failed run does not stop the ones after it.

To compare settings on one take, open **Compare settings on this take** under the button, tick the detectors, smoothers and RTMPose modes, type the detect-every values (`1, 5`), and press **Queue these runs**. It queues one run per combination, and says how many before you press it. Each detector setting gets its own output folder, the one in step 11 with a suffix such as `-mediapipe` or `-rtmpose-balanced-every5`, so no run overwrites another. The second smoother of each setting runs in that same folder with Resume on, reusing its detection, so it takes seconds.[^28]

When the default output folder is still in the box, each run queued gets a new one with the current time, plus `-2`, `-3` if two are queued in the same minute; a folder typed or chosen by hand is used as it is.

The bar follows detection frame by frame, then jumps through sync, calibration, triangulation and writing.[^10] Detection is three quarters of the bar because it is nearly all of the wall time.[^11] Under the bar, one line per video says where it is: waiting, detecting (with the frame), done (with the seconds it took), reused (saved joints from an earlier run) or failed, with the reason. The videos are detected several at a time, so the lines move independently; a video that fails does not stop the others, and the run ends after detection with a message naming every failed file.[^21] The log is everything the pipeline printed, the same lines a terminal run shows.

**Cancel this run** stops the pipeline and the detection workers it started, and the queue moves on to the next run; **Stop the queue** does the same and drops every run still waiting. A cancelled run leaves whatever stage files it had finished, which Resume can pick up.[^12]

## 4. Read the result

The skeleton of the run that finished last plays as soon as it finishes; the line under the heading says which run it is. Drag to rotate, wheel to zoom, the slider scrubs, Play/Pause toggles. The figure is the BVH the pipeline wrote, in metres on a grid of half-metre squares.[^13]

Under the viewer, the numbers from `out3d.metrics.json`, stage by stage, so a poor take can be traced to its cause.[^22] **At a glance** has the ones the processing guide asks for, coloured by its thresholds:[^14]

| Number | Green | Red |
|---|---|---|
| Calibration error, worst camera | 3 px or under | 10 px or over |
| Triangulation error, mean | 3 px or under | 10 px or over |
| Bone length spread | 10 mm or under | 20 mm or over |
| Joints missing | 5 % or under | 15 % or over |
| Upright frames for height | 30 or more | 10 or under |

Then, per stage: how well each camera saw the performer (frames with nobody detected, mean confidence, seconds taken); the clap times and where they came from; each camera's calibration error and whether an old calibration was reused (in which case the height was not applied); the triangulation error with the worst joints and the joints most often missing; what smoothing did (jitter before and after, gaps filled, gaps left); and the least rigid bones. Reading the error backwards like this answers "which camera, which joint, which stage" from one run.

**Rerun with the other smoother** queues the take again with Resume on and the smoother switched: the joints, clap times, calibration and 3D points are reused, only the smoothing and the skeleton are redone, so it takes seconds. The library (section 5) then has both runs; lower jitter with the same bone spread is the better filter for that take ("Choosing the smoother" in `backend/mocap_pipeline/README.md`). It is offered for runs made since the app opened, not for ones opened from the library.

Write the glance numbers in the session log with a word on how the take looked. **Open the output folder** reveals the run's folder in the file manager (open it to see the files); **Run another take** scrolls back to section 2 with the same folder listed.

## 5. Compare runs in the library

The **Library** at the bottom lists every run in `backend/output`, and in any other folder the app wrote to since it opened, one row per run: when it started, the take (the folder the videos came from), the detector and its RTMPose settings, the smoother, cameras, status, the whole time, the detection time, the detection speed in video frames per second (all cameras together), and the accuracy numbers of section 4 with the same colours, plus the jitter before and after smoothing. It reads each run's `out3d.metrics.json`, so runs from the terminal and runs from before this feature are there too, and it is still there after the app is closed.[^29]

Click a heading to sort by it; click again to reverse. **Take** filters to one take, **Finished runs only** hides failed ones, **Refresh** reads the folders again (the library refreshes by itself after each run). **View** plays that run and shows its numbers in section 4; **Folder** reveals its files.

A run into a folder that already has one overwrites its metrics and skeleton, so the app keeps a copy of both in `runs/<start time>/` inside the output folder, before and after every run, and the library reads those copies too. A resumed run's time is marked "(resumed)" and has no detection time or speed: it reused an earlier detection, so it says nothing about the detector's speed.[^29]

## When it fails

The result panel shows the pipeline's message and opens the log. The messages and what to do about them are the table in [filming.md](filming.md), section 11; for the clap and calibration failures the panel shows the message and then the advice line that follows it.[^15] If it says a process was stopped abruptly, the computer most likely ran out of memory: close other programs, or set **Videos detected at once** (step 10) to 1, and run again. If the app says it could not start Python, the backend is not set up on this machine: [mac-setup.md](mac-setup.md). On Windows, check that `backend\.venv\Scripts\python.exe` exists.

## Working on the app

`npm run preview` in `desktop/` serves the page at http://localhost:5174 in a browser with a mocked pipeline that replays a real run's printed lines, for changing the page without Electron.[^16] `npm test` runs the progress parser, the check-output parser and the metrics panel against those lines and a sample `metrics.json`, plus the command line the app builds, its folder listing, how it reads the clap-times box, the comparison matrix and its folders, the library's copies and scan of the output folders, and the library table's sorting, filtering and colours. `npm run typecheck` checks both the page and the Electron side. The backend's own suite also drives the app's compiled runner and progress parser against the real pipeline (`backend/tests/test_desktop_tester.py`): [testing-the-backend.md](testing-the-backend.md).

---
## Sources

[^1]: `desktop/src/main/pipeline.ts`, `pipelineArgs`: the command is `python -u -m mocap_pipeline.run_pipeline <videos> --height-m … --out <folder>/out3d.json --calibration <folder>/calibration.json --detector … --smoother … --fov … --jobs …`, plus `--clap-threshold`, `--sync`, `--recalibrate` and `--resume` when set, run from `backend/`, the same as [processing-a-take.md](processing-a-take.md) step 3.
[^2]: The `electron` package's postinstall downloads the runtime for the platform (https://www.electronjs.org/docs/latest/tutorial/installation). Measured on 2026-10-20 for Electron 33.4.11 on Windows x64: the download, kept in Electron's cache as `electron-v33.4.11-win32-x64.zip`, is 110 MB, and the unpacked `desktop/node_modules/electron/dist` is 269 MB.
[^3]: `desktop/src/main/pipeline.ts`, `resolvePython`: tries `backend/.venv/Scripts/python.exe` then `backend/.venv/bin/python`, then falls back to the PATH.
[^4]: `desktop/src/main/files.ts`, `listVideos` (behind the `list-videos` handler in `main.ts`) sorts with `localeCompare(…, { numeric: true })`. The naming rule is filming.md section 8.
[^5]: `MIN_CAMERAS = 2` in `backend/mocap_pipeline/config.py`; two views are the minimum for triangulation (D-002 on `docs/decisions/DECISIONS.md`). The app refuses to run with fewer (`desktop/src/renderer/main.ts`, `readOptions`).
[^6]: The same limits as the API's upload check, `MIN_HEIGHT_M, MAX_HEIGHT_M = 1.0, 2.5` in `backend/api.py`.
[^7]: `DEFAULT_HFOV_DEG = 65` in `config.py`; iPhone focal lengths come from the file's metadata (`stage2_reconstruct/iphone_camera.py`). The Fold estimate is filming.md section 3.
[^8]: `desktop/src/main/files.ts`, `defaultOutDir` (behind the `default-out-dir` handler in `main.ts`). One folder per take is processing-a-take.md step 1, so takes never share a calibration.
[^9]: The pipeline reuses an existing `--calibration` file unless `--recalibrate` is given, and `--resume` reuses saved stage files whose inputs have not changed (`backend/mocap_pipeline/README.md`, "Rerunning and debugging"; D-023 for the detector check).
[^10]: `backend/mocap_pipeline/stage1_keypoints/detect.py` prints `progress: detect <video> <i>/<n>` every 30 frames when the `MOCAP_PROGRESS` environment variable is set; the app sets it (`pipeline.ts`). The later stages are recognised from the lines `run_pipeline.py` already prints (`desktop/src/shared/progress.ts`).
[^11]: `WEIGHTS` in `desktop/src/shared/progress.ts`: detection 0.75, sync 0.05, calibration 0.08, triangulation 0.05, writing 0.07. Team judgement from the README's "full run, minutes; `--resume` run, seconds"; no timing measurement yet. The `timing` block in `metrics.json` will give the real split once a few takes have run.
[^12]: `desktop/src/main/pipeline.ts`, `cancel()` kills the pipeline's whole process tree (`killTree`: `taskkill /T` on Windows, the process group elsewhere), so the detection workers of `--jobs` stop too; a worker left alive would hold the output pipes open and the window would never get its result. Stage files are written as each stage finishes (`run_pipeline.py`), so a cancelled run keeps the stages before the one it was in.
[^13]: The BVH is written in centimetres, Y up (`stage3_rig/bvh_writer.py`, D-018); the viewer scales any skeleton whose bone offsets exceed five units by 0.01 (`desktop/src/renderer/viewer.ts`).
[^14]: The thresholds are processing-a-take.md step 4, with their own sources there: the synthetic benchmark for the pixel error, Karashchuk et al. 2021 (DOI 10.1016/j.celrep.2021.109730) for limb-length variability, `tests/test_metrics.py` for the missing fraction, `MIN_UPRIGHT_FRAMES` for the upright count. The red limits match the pipeline's own give-up points (`CALIB_MAX_ERROR_PX = 10`, `MIN_UPRIGHT_FRAMES = 10`) or team judgement (20 mm, 15 %); the app colours a value exactly at a limit red, while the pipeline still accepts it.
[^15]: The app keeps the last block of consecutive lines the pipeline wrote to stderr, leaving out tracebacks' code lines, cleanup errors printed at shutdown, Python warnings and library log lines (`desktop/src/shared/progress.ts`, `noteStderr` and `result()`). The clap and calibration `SystemExit` messages in `run_pipeline.py` are two lines, the table's text and then an advice line, so the panel shows both; the scale and floor failures are `ValueError`s from `scale_floor.py`, shown as the traceback's last line. A run killed by a signal (`desktop/src/main/pipeline.ts`, the `close` handler) names the signal above that message; SIGKILL, or a detection process "terminated abruptly" (the pipeline's stage 1 workers), adds the memory advice, because that is how the system stops a program that runs out of memory.
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
[^27]: `desktop/src/main/pipeline.ts`, `pipelineArgs`, passes both only when the detector is RTMPose. The options are `run_pipeline.py`'s; `RTMPOSE_MODE` and `RTMPOSE_DETECT_EVERY` in `config.py` are their defaults. Measured on 2026-11-07 on a Ryzen 9 7950X with the four Chair Spin iPhones detected at once and PR #71's thread fix: balanced with the detector every frame read 18.7 video frames per second in total, every 5 frames 58.1; over 300 frames of two cameras, every 5 moved the joints a median of 2.2 to 2.7 px from every frame.
[^28]: `desktop/src/renderer/main.ts`, `pump`, starts a run only when none is running; `desktop/src/shared/queue.ts`, `expandMatrix`, makes the runs and their folders. One run already detects up to four videos at once, one process each, and each process uses every core (`detect_jobs` in `run_pipeline.py`; PR #71 on ONNX Runtime's threads).
[^29]: `desktop/src/main/library.ts`: `listRuns` reads every `*.metrics.json` in each folder of `backend/output` and in its `runs/` copies; `snapshotRun` makes the copies, and `main.ts` calls it before and after each run. The detection speed is the sum of `stage1.<camera>.frames` over `timing.detect_total_s` (`desktop/src/shared/library.ts`, `detectFps`).
