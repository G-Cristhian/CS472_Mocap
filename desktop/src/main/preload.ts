/** The bridge between the sandboxed page and the main process: exactly the Backend interface. */
import { contextBridge, ipcRenderer, type IpcRendererEvent } from 'electron'

import type { Backend, Progress, RunOptions } from '../shared/types'

function subscribe<T>(channel: string, callback: (payload: T) => void): () => void {
  const listener = (_event: IpcRendererEvent, payload: T) => callback(payload)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}

const backend: Backend = {
  chooseDirectory: () => ipcRenderer.invoke('choose-directory'),
  listVideos: (dir) => ipcRenderer.invoke('list-videos', dir),
  defaultOutDir: (videoDir) => ipcRenderer.invoke('default-out-dir', videoDir),
  run: (options: RunOptions) => ipcRenderer.invoke('run', options),
  cancel: () => ipcRenderer.invoke('cancel'),
  onLog: (callback) => subscribe<string>('log', callback),
  onProgress: (callback) => subscribe<Progress>('progress', callback),
  readText: (file) => ipcRenderer.invoke('read-text', file),
  openFolder: (target) => ipcRenderer.invoke('open-folder', target),
}

contextBridge.exposeInMainWorld('backend', backend)
