# Setting up the pipeline on a Mac

For the laptop that goes to the recording session. Everything runs locally from the terminal; no server, no account. About twenty minutes, most of it downloads. Do this before the session day, on the network you will have there, because two things download once: the Python packages and, if you use the RTMPose detector, its models.

Works on Apple Silicon and Intel. Every dependency ships a macOS wheel, so nothing is compiled.

## 1. Python 3.12

Check what you have:

```
python3 --version
```

3.10 to 3.12 work; 3.12 is what the project pins. If you need it, install from https://www.python.org/downloads/macos/ or with Homebrew (`brew install python@3.12`). Note which command runs it afterwards (`python3.12` with Homebrew).

## 2. Clone and create the environment

```
git clone https://github.com/G-Cristhian/CS472_Mocap.git
cd CS472_Mocap/backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r mocap_pipeline/requirements.txt -r requirements-api.txt pytest
```

The venv lives in `backend/.venv` and is ignored by git. Every later terminal needs `source backend/.venv/bin/activate` first; the prompt shows `(.venv)` when it is active.

Once pull request #21 is merged this becomes `backend/setup.sh`, one command. The lines above do the same thing by hand.

## 3. Prove it works, no footage needed

From `backend/`, with the venv active:

```
python -m pytest tests -q
python -m tests.evaluate_synthetic --quick
```

The tests take about a minute. The benchmark runs stages 2 and 3 on a synthetic performer and prints a table of errors for several camera layouts; the first rows should show a calibration error under 1 px and MPJPE of a few millimetres. If both run, the pipeline is ready.

## 4. The pose model

The MediaPipe model file ships in the repository (`backend/landmarks_from_image_test/models/pose_landmarker_heavy.task`) and is the default, so nothing to download. If you plan to compare detectors (see [comparing-pose-models.md](comparing-pose-models.md)), run RTMPose once now so it downloads its models into `~/.cache/rtmlib` while you have internet:

```
python -c "from mocap_pipeline.stage1_keypoints.backends import create_backend; create_backend('rtmpose').close(); print('rtmpose ready')"
```

## 5. The viewer (optional at the venue)

To watch a result on the laptop you need Node. Check `node --version`; install from https://nodejs.org if missing. Then:

```
cd frontend
npm install
npm run dev
```

Open the address it prints, open a project, and use "Open .bvh / .json" at the bottom right of the viewport. Blender also opens the `.bvh` (File, Import, Motion Capture).

## 6. On the day

- `check_videos` runs on the laptop at the venue and takes seconds per take: [filming.md](filming.md), section 9.
- The full pipeline takes minutes per take and does not need the venue: [processing-a-take.md](processing-a-take.md).
- Keep the laptop plugged in while detecting; MediaPipe on a 60 fps 1080p take uses every core for several minutes.

## If something fails

- `pip` cannot find a wheel: the Python version is outside 3.10 to 3.12, or the venv is not active.
- `ImportError: ... libGL` on a Linux laptop, not a Mac: `sudo apt install libegl1 libgles2 libgl1`.
- `check_videos` says a `.MOV` has no lens metadata: the file was re-exported on the way off the phone; copy the original again (filming.md, section 8).
