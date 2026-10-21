const { app, BrowserWindow, dialog, ipcMain, session, shell } = require('electron');
const path = require('node:path');
const { spawn } = require('node:child_process');
const http = require('node:http');
const fs = require('node:fs');

let mainWindow = null;
let pythonProcess = null;
const SERVER_HOST = '127.0.0.1';
const SERVER_PORT = 8000;

function resolvePython() {
  if (process.env.PYTHON && fs.existsSync(process.env.PYTHON)) {
    return process.env.PYTHON;
  }
  const backendDir = path.resolve(__dirname, '..', '..');
  const candidates = [
    path.join(backendDir, '.venv', 'bin', 'python'),
    path.join(backendDir, '.venv', 'Scripts', 'python.exe'),
    path.join(backendDir, '..', '.venv', 'bin', 'python'),
    path.join(backendDir, '..', '.venv', 'Scripts', 'python.exe'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function checkServerRunning() {
  return new Promise((resolve) => {
    const req = http.get(`http://${SERVER_HOST}:${SERVER_PORT}/health`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(800, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForServer(maxRetries = 30, intervalMs = 250) {
  for (let i = 0; i < maxRetries; i++) {
    const running = await checkServerRunning();
    if (running) return true;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}

function startBackendServer() {
  const python = resolvePython();
  const backendDir = path.resolve(__dirname, '..', '..');
  console.log(`[Main] Spawning Python server using: ${python} in ${backendDir}`);

  const existingPythonPath = process.env.PYTHONPATH || '';
  const pythonPath = existingPythonPath
    ? `${backendDir}${path.delimiter}${existingPythonPath}`
    : backendDir;

  pythonProcess = spawn(
    python,
    ['-u', '-m', 'live_stream_test.server', '--port', String(SERVER_PORT), '--host', SERVER_HOST],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: pythonPath,
      },
      stdio: 'pipe',
    }
  );

  pythonProcess.stdout?.on('data', (d) => {
    console.log(`[Server] ${d.toString().trim()}`);
  });

  pythonProcess.stderr?.on('data', (d) => {
    console.error(`[Server ERR] ${d.toString().trim()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Server] Exited with code ${code}`);
    pythonProcess = null;
  });
}

function killPythonProcess() {
  if (pythonProcess && !pythonProcess.killed) {
    console.log('[Main] Terminating background Python server...');
    try {
      pythonProcess.kill('SIGTERM');
      const proc = pythonProcess;
      setTimeout(() => {
        if (proc && !proc.killed) {
          try {
            proc.kill('SIGKILL');
          } catch (_) {}
        }
      }, 2000);
    } catch (e) {
      console.error(e);
    }
    pythonProcess = null;
  }
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 960,
    minHeight: 650,
    backgroundColor: '#0a0d14',
    title: 'Mocap Live Studio (MediaPipe)',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

ipcMain.handle('select-calibration-file', async () => {
  if (!mainWindow) return null;
  const res = await dialog.showOpenDialog(mainWindow, {
    title: 'Select calibration.json',
    filters: [{ name: 'JSON Calibration', extensions: ['json'] }],
    properties: ['openFile'],
  });
  return res.canceled || res.filePaths.length === 0 ? null : res.filePaths[0];
});

ipcMain.handle('select-video-file', async () => {
  if (!mainWindow) return null;
  const res = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Video File for Stream Testing',
    filters: [
      { name: 'Video Files', extensions: ['mp4', 'mov', 'avi', 'mkv', 'webm'] },
      { name: 'All Files', extensions: ['*'] },
    ],
    properties: ['openFile'],
  });
  return res.canceled || res.filePaths.length === 0 ? null : res.filePaths[0];
});

ipcMain.handle('get-server-url', () => {
  return `ws://${SERVER_HOST}:${SERVER_PORT}/ws`;
});

ipcMain.handle('open-item', async (event, fullPath) => {
  if (fullPath && fs.existsSync(fullPath)) {
    shell.showItemInFolder(fullPath);
    return true;
  }
  return false;
});

ipcMain.handle('open-folder', async (event, dirPath) => {
  if (dirPath && fs.existsSync(dirPath)) {
    shell.openPath(dirPath);
    return true;
  }
  return false;
});

app.whenReady().then(async () => {
  // Allow webcam access automatically in Electron
  if (session && session.defaultSession) {
    session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
      if (permission === 'media') {
        return callback(true);
      }
      callback(true);
    });
  }

  const isRunning = await checkServerRunning();
  if (!isRunning) {
    console.log('[Main] Backend server not detected. Launching local server...');
    startBackendServer();
    const ready = await waitForServer(40, 200);
    if (!ready) {
      console.warn('[Main] Backend server did not respond to /health within 8 seconds.');
    } else {
      console.log('[Main] Backend server is ready.');
    }
  } else {
    console.log('[Main] Backend server is already running.');
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  killPythonProcess();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killPythonProcess();
});

