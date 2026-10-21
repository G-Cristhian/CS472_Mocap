const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectCalibrationFile: () => ipcRenderer.invoke('select-calibration-file'),
  selectVideoFile: () => ipcRenderer.invoke('select-video-file'),
  getServerUrl: () => ipcRenderer.invoke('get-server-url'),
  openItem: (path) => ipcRenderer.invoke('open-item', path),
  openFolder: (path) => ipcRenderer.invoke('open-folder', path),
});
