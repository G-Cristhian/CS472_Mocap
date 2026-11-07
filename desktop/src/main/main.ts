/**
 * Electron main process: one window, and the file-system and process work the
 * page is not allowed to do itself (contextIsolation stays on; see preload.ts).
 */
import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { promises as fs } from 'node:fs'
import path from 'node:path'

import { defaultOutDir, isResultFile, listVideos } from './files'
import { listRuns, snapshotRun } from './library'
import { BACKEND_DIR, runCheck, runPipeline, type RunHandle } from './pipeline'
import type { RunOptions, VideoFile } from '../shared/types'

let running: RunHandle | null = null
/** output folders written this session, so the library lists them even outside backend/output */
const sessionFolders = new Set<string>()

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

ipcMain.handle('choose-output-directory', async (event, current: string) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  const result = await dialog.showOpenDialog(win!, {
    title: 'Choose the folder for this run’s results',
    // the default output folder does not exist until the run makes it: open where it will go
    defaultPath: current || BACKEND_DIR,
    buttonLabel: 'Use this folder',
    // createDirectory: the New Folder button on macOS; promptToCreate: a typed new name on Windows
    properties: ['openDirectory', 'createDirectory', 'promptToCreate'],
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
  // a run from before snapshots existed (or from the terminal) is about to be overwritten: keep it
  await snapshotRun(options.outDir).catch(() => undefined)
  if (running) throw new Error('A run is already in progress')
  sessionFolders.add(options.outDir)
  running = runPipeline(
    options,
    (line) => send('log', line),
    (progress) => send('progress', progress),
  )
  try {
    return await running.done
  } finally {
    running = null
    // keep this run's numbers and skeleton even if a later run reuses the folder (library.ts)
    await snapshotRun(options.outDir).catch((e) => send('log', `Could not keep a copy of the results: ${e}`))
  }
})

ipcMain.handle('list-runs', () => listRuns([path.join(BACKEND_DIR, 'output')], [...sessionFolders]))

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
