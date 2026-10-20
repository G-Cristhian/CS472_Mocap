# Testing the backend

For developers changing anything under `backend/` or `desktop/`: what to run before opening a pull request, and after pulling someone else's. Two parts: the automated suite, which needs no footage and takes about two minutes, and one run on real footage through the desktop tester, which is how the backend is tested by hand.

Before this: the backend environment exists ([mac-setup.md](mac-setup.md), steps 1 to 3; on Windows the venv is `backend\.venv` and the command is `python`), Node is installed, and `npm install` has been run once in `desktop/` ([desktop-tester.md](desktop-tester.md), step 1).

## 1. The automated suite

From `backend/`, with the venv active:

```
python -m pytest tests -q
```

Everything runs on synthetic data: a performer with exactly known joints seen by virtual phones for stages 2 and 3, encoded videos with a clap for the clap search and `check_videos`, the API through FastAPI's test client with the pipeline stubbed, and the desktop tester's compiled code driven by Node.[^1] The desktop tests do two things. They replay the lines a real run prints through the tester's progress tracker, so a renamed `print` in `run_pipeline.py` that would freeze the progress bar fails here instead of at a session. And they let the tester's own runner spawn `python -m mocap_pipeline.run_pipeline` on two synthetic videos, in which MediaPipe finds nobody: the run ends at calibration with the message filming.md lists, the tester must show it, and Cancel must stop the detection workers.[^2]

What you should see: all passed, about two minutes.[^3] If the desktop tests are reported as skipped, Node is not on the PATH or `npm install` was not run in `desktop/`. To leave them out on purpose:

```
python -m pytest tests -q -m "not desktop"
```

The tester also has its own unit tests, without Python:

```
cd desktop
npm test
npm run typecheck
```

## 2. A run on real footage

The suite never sees a person, so one real take goes through the tester before a pull request that touches a stage. Any take folder from a session will do; the shortest one is fine. Follow [desktop-tester.md](desktop-tester.md): check the videos, run with the defaults, then read the glance numbers before you watch.[^4]

Compare them with the numbers written in the session log for that take ([processing-a-take.md](processing-a-take.md), step 4). A pull request that changes them says so and why. A failure on a take that passed before the change is a regression, whatever the message; the tester shows the pipeline's own message and opens the log, and the table in [filming.md](filming.md) section 11 says what each message means.

## 3. What to put in the pull request

- The last line of `pytest` (counts and time) and of `npm test`.
- For a change to a stage: the take you ran and its glance numbers, before and after.
- For a new printed line the progress bar should follow, or a new stage file: the parser is `desktop/src/shared/progress.ts`, its unit test `desktop/test/progress.test.cjs`, and `backend/tests/test_desktop_tester.py` asserts on the lines the real run prints, so all three change together.

---
## Sources

[^1]: `backend/tests/`: `test_synthetic_pipeline.py` (stages 2 and 3 against the truth, `synthetic_scene.py`), `test_check_videos.py` (encoded videos from `synthetic_video.py`), `test_api.py` (FastAPI test client, `run` replaced), `test_desktop_tester.py` (Node runs `desktop/test/harness.cjs`, which loads the compiled `desktop/dist/main`; the fixture compiles it with the tester's own TypeScript first).
[^2]: The tester sets `MOCAP_PROGRESS=1` so `stage1_keypoints/detect.py` prints a progress line every 30 frames; the failure message is the `SystemExit` raised in `run_pipeline.calibrate_cameras` when no board videos are given. The tester takes the last stderr line as the error, so the second line of that message ("Record the ChArUco board…") is what the window shows; the reason is the line before it in the log. Cancel kills the pipeline's whole process tree (`desktop/src/main/pipeline.ts`, `killTree`), because stage 1 runs each video in its own process (`--jobs`) and a worker left alive holds the output pipes open, so the window would never get its result.
[^3]: Measured on 2026-10-19 on a Windows laptop: 131 tests in 62 s, of which the seven desktop tests take 25 s (four of them spawn the real pipeline with MediaPipe).
[^4]: The glance numbers and their thresholds are desktop-tester.md step 4, the same as processing-a-take.md step 4.
