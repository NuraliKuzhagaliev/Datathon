const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('launcher', Object.freeze({
  start: (mode, url) => ipcRenderer.invoke('cashproof:start', { mode, url }),
  onStatus: listener => {
    const handler = (_event, status) => listener(status);
    ipcRenderer.on('cashproof:status', handler);
    return () => ipcRenderer.removeListener('cashproof:status', handler);
  },
}));
