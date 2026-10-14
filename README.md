# CS472 Mocap

CS472 Mocap turns synchronized videos from multiple phones or webcams into 3D motion capture. The Python backend detects pose landmarks, reconstructs and rigs a skeleton, and exports animation for a React/Three.js web viewer.

## Setup

From the repository root, run:

```bash
./backend/setup.sh
```

This installs uv if needed, downloads Python 3.12, and installs the pinned dependencies from `backend/requirements.txt` into `backend/.venv`. Rerunning it reuses the environment. Bash, curl, and internet access are required.

## Run tests

```bash
source backend/.venv/bin/activate
python -m pytest backend/tests -q
```

Tests use synthetic data; videos and a MediaPipe model are not needed.

## Run API

After activating the environment from the repository root:

```bash
cd backend && uvicorn api:app
```

## Run frontend

In another terminal, with Node.js and npm installed:

```bash
cd frontend
npm install
npm run dev
```

Use `npm run build` for a production build and `npm run preview` to preview it.

See the [field-test protocol](docs/field-test-protocol.md) for camera placement, recording, and pipeline instructions.
