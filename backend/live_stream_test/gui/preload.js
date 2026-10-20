const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectCalibrationFile: () => ipcRenderer.invoke('select-calibration-file'),
  selectVideoFile: () => ipcRenderer.invoke('select-video-file'),
  getServerUrl: () => ipcRenderer.invoke('get-server-url'),
});
