# MediaPipe Live Stream Studio

Real-time multi-camera motion capture studio with MediaPipe pose estimation, live 2D skeleton overlays, One-Euro jitter filtering, and interactive 3D spatial viewport.

## Features

- **Multi-Camera Grid**: Connect multiple cameras (local USB/built-in webcams or mobile RTSP/HTTP streams).
- **MediaPipe Pose Estimation**: Real-time 33-landmark pose tracking running in VIDEO mode.
- **2D Skeleton Overlays**: Real-time glowing bones and joint confidence rendering on each camera view.
- **3D Spatial Viewport**: Interactive Three.js 3D viewport with orbit controls, floor grid, axes, and presets.
- **1-Euro Jitter Filter**: Real-time causal filtering (Casiez et al. 2012) eliminating jitter at rest while keeping responsiveness during fast motions.
- **Multi-Camera Triangulation**: Option to load `calibration.json` from `mocap_pipeline` for real metric multi-view 3D reconstruction, with automatic fallback to MediaPipe 3D world landmarks.
- **Hardware Auto-Detection**: Instant scan and quick-connect for detected webcams.

## Architecture

```
backend/live_stream_test/
├── server.py              # FastAPI server (WebSocket @ /ws + REST API + MJPEG)
├── camera_stream.py       # CameraManager & multi-threaded non-blocking capture workers
├── detector.py            # MediaPipe PoseLandmarker wrapper (lite, full, heavy models)
├── filter.py              # OneEuroFilter for smooth 3D tracking
├── triangulate_live.py    # Real-time multi-view triangulation using CameraRig
├── run_live.bat           # One-click Windows launch script
└── gui/                   # Dedicated Electron GUI application
    ├── main.js            # Electron main process (auto-spawns Python backend if needed)
    ├── preload.js         # Safe IPC bridge
    ├── index.html         # Studio layout & modals
    ├── style.css          # Modern dark-mode UI with glassmorphism & rich tokens
    ├── renderer.js        # WebSocket client, 2D Canvas overlays, Three.js 3D viewport
    └── lib/               # Bundled Three.js and OrbitControls
```

## How to Run

### Option 1: One-Click Launcher
- **Linux / macOS:**
  ```bash
  ./backend/live_stream_test/run_live.sh
  ```
- **Windows:**
  Double-click `run_live.bat` or run:
  ```cmd
  backend\live_stream_test\run_live.bat
  ```

### Option 2: From `desktop/` directory (Cross-Platform)
```bash
cd desktop
npm run live
```

### Option 3: Manual Startup
1. **Start the Python Backend Server:**
   - **Linux / macOS:**
     ```bash
     cd backend
     ./.venv/bin/python -m live_stream_test.server --port 8000
     ```
   - **Windows:**
     ```cmd
     cd backend
     .\.venv\Scripts\python.exe -m live_stream_test.server --port 8000
     ```

2. **Launch the Electron GUI:**
   - **Linux / macOS:**
     ```bash
     cd desktop
     npx electron ../backend/live_stream_test/gui
     ```
   - **Windows:**
     ```cmd
     cd desktop
     npx.cmd electron ..\backend\live_stream_test\gui
     ```

## Adding Cameras

1. In the top bar, click **"Add Camera"**.
2. **Local Webcams**: Select any detected webcam from the list (e.g. `Camera 0`, `Camera 1`) or type a custom camera index.
3. **Phone / Network Cameras**: Switch to the **Network Stream** tab and input an RTSP or HTTP URL:
   - Android: Use apps like *IP Webcam* (`http://<ip>:8080/video`) or *DroidCam*.
   - iOS: Use RTSP streaming apps or OBS virtual camera.
4. Click **"Connect Camera"**. The feed will appear in the grid and immediately start tracking joints.

## 3D Spatial Tracking & Calibration

- By default, the 3D viewport displays MediaPipe's metric 3D world landmarks from the primary active camera.
- If you have an existing `calibration.json` produced by `mocap_pipeline`:
  1. Click **"Settings"** in the top bar.
  2. Click **"Browse..."** to select your `calibration.json` file.
  3. Click **"Load"**.
  4. When 2 or more calibrated cameras view the performer, the 3D viewport automatically switches to **Multi-View Triangulated 3D**.
