# Testing the backend with the desktop app

For anyone who wants to run the pipeline on a take without the terminal or the web app, and see the result at once. The app lives in `desktop/`; it runs the same command the terminal procedures use and leaves the same files behind, so a take processed here is processed exactly as in [processing-a-take.md](processing-a-take.md).[^1]

Before step 1: Node is installed (the frontend needs it too), the backend works ([mac-setup.md](mac-setup.md), through step 3), and the take's videos are in one folder, originals, named with the camera number first ([filming.md](filming.md), section 8).

## 1. Install and start

Once per machine:

```
cd desktop
npm install
```

The first install downloads Electron, about 100 MB.[^2] Then, every time:

```
npm start
```

That builds the app and opens the window. It finds Python on its own: the backend's virtual environment if `backend/.venv` exists, otherwise whatever `python3` (or `python` on Windows) is on the PATH.[^3]

## 2. Pick the take

1. **Choose folder…** and pick the take's folder. Every `.mov` and `.mp4` in it is listed, sorted by name with numbers in natural order, so `cam2` comes before `cam10`.[^4] The list order is the camera order the pipeline gets, camera 0 first; the arrows move a file up or down, the tick leaves it out.
2. At least two videos must be ticked.[^5]
3. **Performer height** in metres, from the take log; the app accepts 1 to 2.5.[^6]
4. **Detector**: MediaPipe unless you are comparing models ([comparing-pose-models.md](comparing-pose-models.md)).
5. **Smoother**: Savitzky-Golay unless you are comparing filters. Butterworth is the other; run the take once, then again with Resume on and the other smoother, and compare `jitter_mm` in `metrics.json` and the fast moments in the preview ("Choosing the smoother" in `backend/mocap_pipeline/README.md`).
6. **Field of view**: only used for cameras without iPhone lens metadata; 65 is the pipeline's default, the Fold is about 75.[^7]
7. **Output folder**: defaults to `backend/output/<folder name>-<date and time>`, one folder per take.[^8] Change it to reprocess into a folder you already have.
8. **Recalibrate** is on by default so a stale `calibration.json` in the output folder is never reused by accident; **Resume** reuses the stage files already in that folder, which turns a rerun into seconds.[^9]

## 3. Run

The bar follows detection frame by frame, then jumps through sync, calibration, triangulation and writing.[^10] Detection is three quarters of the bar because it is nearly all of the wall time.[^11] The text beside the stage pill says which file and frame it is on; the log under the bar is everything the pipeline printed, the same lines a terminal run shows.

**Cancel** stops the Python process; a cancelled run leaves whatever stage files it had finished, which Resume can pick up.[^12]

## 4. Read the result

The skeleton plays as soon as the run finishes. Drag to rotate, wheel to zoom, the slider scrubs, Play/Pause toggles. The figure is the BVH the pipeline wrote, in metres on a one-metre grid.[^13]

Under the viewer, four numbers from `out3d.metrics.json`, coloured by the processing guide's thresholds:[^14]

| Number | Green | Red |
|---|---|---|
| Calibration error, worst camera | under 3 px | over 10 px |
| Bone length spread | under 10 mm | over 20 mm |
| Joints missing | under 5 % | over 15 % |
| Upright frames for height | 30 or more | under 10 |

Write them in the session log with a word on how the take looked. **Open the output folder** shows every file the run produced; **Run another take** goes back to step 2 with the same folder listed.

## When it fails

The result panel shows the pipeline's own message and opens the log. The messages and what to do about them are the table in [filming.md](filming.md), section 11; they are the same whether the run came from the app or the terminal.[^15] If the app says it could not start Python, the backend is not set up on this machine: [mac-setup.md](mac-setup.md).

## Working on the app

`npm run preview` in `desktop/` serves the page at http://localhost:5174 in a browser with a mocked pipeline that replays a real run's printed lines, for changing the page without Electron.[^16] `npm test` runs the progress parser against those lines. `npm run typecheck` checks both the page and the Electron side.

---
## Sources

[^1]: `desktop/src/main/pipeline.ts`, `pipelineArgs`: the command is `python -u -m mocap_pipeline.run_pipeline <videos> --height-m … --out <folder>/out3d.json --calibration <folder>/calibration.json --detector … --smoother … --fov …`, run from `backend/`, the same as [processing-a-take.md](processing-a-take.md) step 3.
[^2]: The `electron` package's postinstall downloads the runtime for the platform (https://www.electronjs.org/docs/latest/tutorial/installation).
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
