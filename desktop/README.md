# Mocap backend tester

A small desktop app for testing `backend/mocap_pipeline` without the web app: choose a folder of videos, run the pipeline, watch a progress bar with the current step, then play the resulting skeleton with a time bar. Drag to rotate, wheel to zoom.

It runs the same command the procedures use (`python -m mocap_pipeline.run_pipeline …`) from `backend/`, with the backend's own virtual environment if `backend/.venv` exists. Every artifact goes to the output folder shown in the form, one folder per take, so the result is exactly what a terminal run would leave behind.

## Run it

Needs Node (the frontend needs it too) and a working backend ([docs/procedures/mac-setup.md](../docs/procedures/mac-setup.md)).

```
cd desktop
npm install
npm start
```

`npm start` builds and opens the window. The first `npm install` downloads Electron, about 100 MB.

1. **Choose folder**: a folder holding one take, one video per camera. Files are listed sorted by name, which the filming protocol makes camera order; untick the ones to leave out, reorder with the arrows. At least two.
2. Height, detector, field of view for non-iPhone cameras, the output folder (defaults to `backend/output/<folder name>-<time>`), recalibrate, resume.
3. **Run**. The bar follows detection frame by frame (the pipeline prints a progress line every 30 frames when `MOCAP_PROGRESS` is set, which this app sets), then the later stages. The log is under the bar.
4. The result plays with a time bar and the four quality numbers from `out3d.metrics.json`, coloured by the thresholds in [processing-a-take.md](../docs/procedures/processing-a-take.md). "Open the output folder" shows the files.

A failed run shows the pipeline's own message (the same ones listed in filming.md section 11) and opens the log.

## Working on it

- `npm run preview` serves the page in a browser at http://localhost:5174 with a mocked pipeline (`src/renderer/mock.ts`) that replays a real run's lines, for UI work without Electron. The sample BVH comes from `frontend/public/samples`.
- `npm test` compiles the main process and runs the progress parser tests (`test/`).
- `npm run typecheck` checks both the page and the main process.

Layout: `src/main` is the Electron side (window, dialogs, spawning Python), `src/renderer` is the page (plain TypeScript, three.js for the preview), `src/shared` is what both use, including the progress parser that turns the pipeline's printed lines into the bar.
