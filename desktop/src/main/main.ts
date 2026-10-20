/**
 * Electron main process: one window, and the file-system and process work the
 * page is not allowed to do itself (contextIsolation stays on; see preload.ts).
 */
import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { promises as fs } from 'node:fs'
import path from 'node:path'

import { defaultOutDir, isResultFile, listVideos } from './files'
import { BACKEND_DIR, runCheck, runPipeline, type RunHandle } from './pipeline'
import type { RunOptions, VideoFile } from '../shared/types'

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

ipcMain.handle('list-videos', (_event, dir: string): Promise<VideoFile[]> => listVideos(dir))

ipcMain.handle('default-out-dir', async (_event, videoDir: string): Promise<string> => defaultOutDir(BACKEND_DIR, videoDir))

ipcMain.handle('check-videos', async (event, videos: string[], clapThreshold: number) => {
  if (running) throw new Error('A run is already in progress')
  const send = (channel: string, payload: unknown) => {
    if (!event.sender.isDestroyed()) event.sender.send(channel, payload)
  }
  return runCheck(videos, clapThreshold, (line) => send('log', line))
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
  if (!isResultFile(file)) throw new Error('Only result files can be read')
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
