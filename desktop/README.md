# Mocap backend tester

A small desktop app for testing `backend/mocap_pipeline` without the web app: choose a folder of videos, run the pipeline, watch a progress bar with the current step, then play the resulting skeleton with a time bar. Drag to rotate, wheel to zoom.

It runs the same command the procedures use (`python -m mocap_pipeline.run_pipeline …`) from `backend/`, with the backend's own virtual environment if `backend/.venv` exists. Every artifact goes to the output folder shown in the form, one folder per take, so the result is exactly what a terminal run would leave behind.

## Run it

Needs Node (the frontend needs it too) and a working backend ([docs/procedures/mac-setup.md](../docs/procedures/mac-setup.md)).

On a Mac:

```
cd ~/CS472_Mocap/desktop
npm install
npm start
```

On Windows, in PowerShell:

```
cd $HOME\CS472_Mocap\desktop
npm.cmd install
npm.cmd start
```

Use the folder you cloned into if it is not your home folder. `npm start` builds and opens the window. The first `npm install` downloads Electron, about 110 MB. On Windows, type `npm.cmd` wherever this page says `npm`: PowerShell blocks `npm` itself by default. The step-by-step version, with the errors you may see and what they mean, is [docs/procedures/desktop-tester.md](../docs/procedures/desktop-tester.md).

1. **Choose folder**: a folder holding one take, one video per camera. Files are listed sorted by name, which the filming protocol makes camera order; untick the ones to leave out, reorder with the arrows. At least two.
2. **Check the videos** (optional, seconds): runs `mocap_pipeline.check_videos` on the ticked files and shows resolution, frame rate, lens metadata and the clap time per file, plus the cross-camera warnings.
3. Height, detector, smoother, field of view for non-iPhone cameras, the clap loudness threshold (`--clap-threshold`), clap times typed by hand (`--sync`), how many videos to detect at once (`--jobs`, 0 = automatic), the output folder (defaults to `backend/output/<folder name>-<time>`), recalibrate, resume. With Recalibrate off and an existing `calibration.json`, the height is ignored, and the form says so.
4. **Run the pipeline**. The bar follows detection frame by frame (the pipeline prints a progress line every 30 frames when `MOCAP_PROGRESS` is set, which this app sets), then the later stages. One line per video shows waiting, detecting, done, reused or failed with the reason; a failed file does not stop the others. The log is under the bar.
5. The result plays with a time bar, then the numbers from `out3d.metrics.json` stage by stage (per camera, per joint, jitter before and after smoothing, gaps, timing), the glance numbers coloured by the thresholds in [processing-a-take.md](../docs/procedures/processing-a-take.md). "Rerun with the other smoother" repeats the run with Resume on and the smoother switched, and a table compares the runs of the take. "Open the output folder" shows the files.

A failed run shows the pipeline's own message (the same ones listed in filming.md section 11) and opens the log.

## Working on it

- `npm run preview` serves the page in a browser at http://localhost:5174 with a mocked pipeline (`src/renderer/mock.ts`) that replays a real run's lines, for UI work without Electron. The sample BVH comes from `frontend/public/samples`.
- `npm test` compiles the main process and runs the tests in `test/`: the progress parser, the check-output parser, the metrics panel, the command line it builds, the folder listing and the read-back whitelist. No Python needed.
- `npm run typecheck` checks both the page and the main process.
- The backend's suite checks this app against the real pipeline: `cd backend && python -m pytest tests/test_desktop_tester.py` replays what a run prints through the progress tracker and lets the app's own runner spawn the pipeline on synthetic videos (`test/harness.cjs` drives the compiled code). It needs Node and `npm install` here, and skips otherwise; `pytest -m "not desktop"` leaves it out. See [docs/procedures/testing-the-backend.md](../docs/procedures/testing-the-backend.md).

Layout: `src/main` is the Electron side (window, dialogs, spawning Python; `files.ts` is the Electron-free part so the tests can load it), `src/renderer` is the page (plain TypeScript, three.js for the preview), `src/shared` is what both use: the progress parser that turns the pipeline's printed lines into the bar and the per-video states, the parser for what `check_videos` prints, and the metrics summary behind the result panel.
