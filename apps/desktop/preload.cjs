const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('cashproof', Object.freeze({
  getConfig: () => ipcRenderer.invoke('cashproof:config'),
  openSource: url => ipcRenderer.invoke('cashproof:source', url),
  showLauncher: () => ipcRenderer.invoke('cashproof:launcher'),
}));
