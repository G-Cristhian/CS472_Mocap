/**
 * Electron main process: one window, and the file-system and process work the
 * page is not allowed to do itself (contextIsolation stays on; see preload.ts).
 */
import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { promises as fs } from 'node:fs'
import path from 'node:path'

import { BACKEND_DIR, runPipeline, type RunHandle } from './pipeline'
import type { RunOptions, VideoFile } from '../shared/types'

const VIDEO_EXTENSIONS = new Set(['.mov', '.mp4'])
let running: RunHandle | null = null

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 720,
    minHeight: 520,
    title: 'Mocap backend tester',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  void win.loadFile(path.join(__dirname, '..', '..', 'renderer', 'index.html'))
}

ipcMain.handle('choose-directory', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  const result = await dialog.showOpenDialog(win!, {
    title: 'Choose the folder with one take’s videos',
    properties: ['openDirectory'],
  })
  return result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0]
})

ipcMain.handle('list-videos', async (_event, dir: string): Promise<VideoFile[]> => {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  const videos: VideoFile[] = []
  for (const e of entries) {
    if (!e.isFile() || !VIDEO_EXTENSIONS.has(path.extname(e.name).toLowerCase())) continue
    const full = path.join(dir, e.name)
    const st = await fs.stat(full)
    videos.push({ path: full, name: e.name, sizeMb: Math.round((st.size / 1024 / 1024) * 10) / 10 })
  }
  // camera order by name: the filming protocol puts the camera number first
  return videos.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
})

ipcMain.handle('default-out-dir', async (_event, videoDir: string): Promise<string> => {
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '').replace(/(\d{8})(\d{4})/, '$1-$2')
  return path.join(BACKEND_DIR, 'output', `${path.basename(videoDir)}-${stamp}`)
})

ipcMain.handle('run', async (event, options: RunOptions) => {
  if (running) throw new Error('A run is already in progress')
  await fs.mkdir(options.outDir, { recursive: true })
  const send = (channel: string, payload: unknown) => {
    if (!event.sender.isDestroyed()) event.sender.send(channel, payload)
  }
  running = runPipeline(
    options,
    (line) => send('log', line),
    (progress) => send('progress', progress),
  )
  try {
    return await running.done
  } finally {
    running = null
  }
})

ipcMain.handle('cancel', async () => {
  running?.cancel()
})

ipcMain.handle('read-text', async (_event, file: string): Promise<string> => {
  if (!path.isAbsolute(file) || !['.bvh', '.json', '.log', '.txt'].includes(path.extname(file).toLowerCase())) {
    throw new Error('Only result files can be read')
  }
  return fs.readFile(file, 'utf8')
})

ipcMain.handle('open-folder', async (_event, target: string) => {
  shell.showItemInFolder(target)
})

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  running?.cancel()
  if (process.platform !== 'darwin') app.quit()
})
