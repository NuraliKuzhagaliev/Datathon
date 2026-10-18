const { app, BrowserWindow, ipcMain, shell, session, dialog } = require('electron');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const Ajv = require('ajv/dist/2020').default;
const { serverOrigin, sourceUrl, insideBundle, backendArguments, checkHealthContract } = require('./security.cjs');

let launcher, viewer, child, activeOrigin, localKey, activeMode, starting = false, quitting = false, quitRequested = false;
let startupController;
const launcherUrl = pathToFileURL(path.join(__dirname, 'launcher.html')).href;
const repo = path.resolve(__dirname, '../..');
const testRoot = !app.isPackaged && process.env.CASHPROOF_DESKTOP_TEST === '1' && process.env.CASHPROOF_DESKTOP_TEST_ROOT ? path.resolve(process.env.CASHPROOF_DESKTOP_TEST_ROOT) : null;
if (testRoot) { fs.mkdirSync(path.join(testRoot, 'user-data'), { recursive: true }); app.setPath('userData', path.join(testRoot, 'user-data')); }
const bundleRoot = testRoot ? path.join(testRoot, 'backend') : app.isPackaged ? path.join(process.resourcesPath, 'backend') : path.join(repo, 'releases/backend');
const frontendRoot = app.isPackaged ? path.join(process.resourcesPath, 'web') : path.join(repo, 'apps/web/dist');
const schemaPath = app.isPackaged ? path.join(process.resourcesPath, 'contracts/desktop-launch.schema.json') : path.join(repo, 'packages/contracts/desktop-launch.schema.json');

function status(message, failed = false) { if (launcher && !launcher.isDestroyed()) launcher.webContents.send('cashproof:status', { message, failed }); }
function isSender(event, window, expected) { return window && !window.isDestroyed() && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame && (expected === launcherUrl ? event.senderFrame.url === launcherUrl : new URL(event.senderFrame.url).origin === expected); }
function secure(window, allowed) {
  window.webContents.setWindowOpenHandler(({ url }) => {
    try { const checked = sourceUrl(url); void shell.openExternal(checked); } catch { /* Never open arbitrary schemes or hosts. */ }
    return { action: 'deny' };
  });
  window.webContents.on('will-navigate', (event, url) => { try { if (!allowed(url)) event.preventDefault(); } catch { event.preventDefault(); } });
  window.webContents.on('will-redirect', (event, url) => { try { if (!allowed(url)) event.preventDefault(); } catch { event.preventDefault(); } });
  window.webContents.on('will-attach-webview', event => event.preventDefault());
}
function showLauncher() {
  if (launcher && !launcher.isDestroyed()) { launcher.show(); launcher.focus(); return; }
  launcher = new BrowserWindow({ width: 850, height: 690, minWidth: 640, minHeight: 600, backgroundColor: '#f7f7f8', icon: path.join(__dirname, 'assets/app.png'), autoHideMenuBar: true, title: 'CashProof — подключение', webPreferences: { preload: path.join(__dirname, 'launcher-preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false } });
  secure(launcher, url => url === launcherUrl);
  void launcher.loadURL(launcherUrl);
}
async function stopOwnedBackend() {
  startupController?.abort();
  const owned = child; child = undefined; localKey = null;
  if (!owned || owned.exitCode !== null || owned.signalCode !== null || !owned.pid) return;
  if (process.platform === 'win32') {
    await new Promise(resolve => {
      const taskkill = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe');
      const killer = spawn(taskkill, ['/PID', String(owned.pid), '/T', '/F'], { shell: false, windowsHide: true, stdio: 'ignore' });
      killer.once('error', () => { owned.kill(); resolve(); }); killer.once('exit', resolve);
    });
  } else owned.kill('SIGTERM');
}
async function openViewer(origin, mode, key) {
  activeOrigin = origin; activeMode = mode; localKey = key;
  viewer = new BrowserWindow({ width: 1440, height: 960, minWidth: 900, minHeight: 700, backgroundColor: '#f7f7f8', icon: path.join(__dirname, 'assets/app.png'), autoHideMenuBar: true, show: false, title: 'CashProof', webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false } });
  secure(viewer, url => new URL(url).origin === activeOrigin);
  viewer.webContents.on('will-prevent-unload', event => {
    const choice = dialog.showMessageBoxSync(viewer, {
      type: 'question', title: 'Несохранённые изменения',
      message: 'В окне есть несохранённые изменения. При продолжении они будут потеряны.',
      buttons: ['Остаться', 'Продолжить без сохранения'], defaultId: 0, cancelId: 0,
    });
    if (choice === 1) event.preventDefault();
    else quitRequested = false;
  });
  viewer.webContents.on('render-process-gone', () => { showLauncher(); status('Окно интерфейса завершилось. Вернитесь к выбору режима.', true); });
  viewer.on('closed', () => {
    viewer = undefined;
    if (quitRequested) finishQuit();
    else { void stopOwnedBackend(); if (!quitting) showLauncher(); }
  });
  await viewer.loadURL(origin);
  viewer.show(); if (launcher && !launcher.isDestroyed()) launcher.hide();
}
async function launchLocal() {
  const manifestFile = path.join(bundleRoot, 'launch.json');
  if (!fs.existsSync(manifestFile)) throw new Error('Локальный сервис анализа не установлен. Установите комплект модели от команды или выберите сервер команды.');
  const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
  const check = new Ajv({ strict: false }).compile(JSON.parse(fs.readFileSync(schemaPath, 'utf8')));
  if (!check(manifest)) throw new Error('launch.json не соответствует контракту 1.0.0.');
  if (Object.keys(manifest.env).some(k => /API.?KEY|TOKEN|SECRET|PASSWORD/i.test(k))) throw new Error('launch.json содержит секретные переменные. Удалите их из комплекта приложения.');
  const executable = insideBundle(bundleRoot, manifest.executable); const cwd = insideBundle(bundleRoot, manifest.cwd);
  if (!fs.statSync(executable).isFile() || !fs.statSync(cwd).isDirectory()) throw new Error('Неверные пути среды выполнения.');
  if (!fs.existsSync(path.join(frontendRoot, 'index.html'))) throw new Error('Веб-сборка отсутствует. Выполните pnpm build:web.');
  const key = randomBytes(32).toString('hex'); const dataDir = path.join(app.getPath('userData'), 'cases');
  fs.mkdirSync(dataDir, { recursive: true });
  status('Запускается локальный сервис. Подготовка подключения…');
  const worker = spawn(executable, backendArguments(manifest.args_prefix, dataDir, frontendRoot), { cwd, shell: false, windowsHide: true, env: { ...process.env, ...manifest.env, CASHPROOF_API_KEY: key, CASHPROOF_MODE: 'offline', HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1' }, stdio: ['ignore', 'pipe', 'pipe'] });
  child = worker;
  // Backend stderr can contain case information. Drain without forwarding to renderer or logs.
  worker.stderr.on('data', () => {});
  worker.on('exit', () => { if (child === worker && !quitting) { status('Локальный сервис остановился. Проверьте среду выполнения, видеокарту и файлы модели на компьютере.', true); if (viewer && !viewer.isDestroyed()) { viewer.close(); } } });
  const port = await new Promise((resolve, reject) => {
    let buffered = ''; let settled = false;
    const timer = setTimeout(() => finish(new Error('Сервис не сообщил HTTP-готовность за 60 секунд. Проверьте bundle.')), 60000);
    function finish(error, port) { if (settled) return; settled = true; clearTimeout(timer); error ? reject(error) : resolve(port); }
    worker.once('error', () => finish(new Error('Не удалось запустить Python runtime. Проверьте путь и установленные компоненты.')));
    worker.once('exit', () => finish(new Error('Backend завершился до запуска HTTP. Проверьте runtime и веса.')));
    worker.stdout.on('data', chunk => {
      buffered += chunk.toString('utf8');
      if (buffered.length > 65536) { finish(new Error('Некорректный протокол запуска backend.')); buffered = ''; return; }
      let end;
      while ((end = buffered.indexOf('\n')) !== -1) {
        const line = buffered.slice(0, end); buffered = buffered.slice(end + 1);
        try { const message = JSON.parse(line); if (message.event === 'http_ready' && Number.isInteger(message.port) && message.port > 0 && message.port <= 65535) finish(null, message.port); } catch { /* Ignore non-handshake output without exposing it. */ }
      }
    });
  });
  const origin = `http://127.0.0.1:${port}`;
  status('Подключение готово. Загружается локальная модель; это может занять несколько минут…');
  const controller = new AbortController(); startupController = controller;
  const started = Date.now();
  while (Date.now() - started < 240000 && !controller.signal.aborted) {
    if (worker.exitCode !== null) throw new Error('Сервис анализа остановился во время загрузки модели.');
    try {
      const response = await fetch(`${origin}/health/ready`, { redirect: 'error', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(4000)]) });
      const health = await response.json();
      checkHealthContract(health);
      if (response.ok && health.ready === true && health.mode === 'offline' && health.contract_version === '1.0.0') { await openViewer(origin, 'offline', key); return; }
    } catch (error) { if (error.code === 'CONTRACT_MISMATCH') throw error; }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  throw new Error('Модель не подтвердила готовность. Проверьте файлы модели, память видеокарты и среду выполнения; затем повторите запуск.');
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { const window = viewer || launcher; if (window) { if (window.isMinimized()) window.restore(); window.show(); window.focus(); } });
  app.whenReady().then(() => {
    session.defaultSession.setPermissionRequestHandler((_web, _permission, callback) => callback(false));
    session.defaultSession.setPermissionCheckHandler(() => false);
    ipcMain.handle('cashproof:start', async (event, input) => {
      if (!isSender(event, launcher, launcherUrl) || starting) throw new Error('Запуск недоступен.');
      starting = true;
      try {
        await stopOwnedBackend();
        if (input?.mode === 'offline') await launchLocal();
        else if (input?.mode === 'connected' && typeof input.url === 'string') { const origin = serverOrigin(input.url); status('Открывается сервер команды…'); await openViewer(origin, 'connected', null); }
        else throw new Error('Выберите режим подключения.');
        return { ok: true };
      } catch (error) {
        await stopOwnedBackend(); if (viewer && !viewer.isDestroyed()) viewer.close();
        const message = error.code === 'ERR_FAILED' ? 'Сервер недоступен. Проверьте URL и соединение.' : error.message;
        status(message, true); return { ok: false, message };
      } finally { starting = false; }
    });
    ipcMain.handle('cashproof:config', event => { if (!isSender(event, viewer, activeOrigin)) throw new Error('Недопустимый источник.'); return { mode: activeMode, apiKey: activeMode === 'offline' ? localKey : null, contractVersion: '1.0.0' }; });
    ipcMain.handle('cashproof:source', async (event, url) => { if (!isSender(event, viewer, activeOrigin) || typeof url !== 'string') throw new Error('Недопустимый источник.'); await shell.openExternal(sourceUrl(url)); });
    ipcMain.handle('cashproof:launcher', event => { if (!isSender(event, viewer, activeOrigin)) throw new Error('Недопустимый источник.'); viewer.close(); });
    showLauncher();
  });
}
function finishQuit() {
  if (quitting) return;
  quitting = true;
  void stopOwnedBackend().finally(() => app.quit());
}
app.on('window-all-closed', () => { if (!starting && !quitting) app.quit(); });
app.on('before-quit', event => {
  if (quitting) return;
  event.preventDefault();
  // The renderer gets to preserve a draft before its owned backend is stopped.
  if (viewer && !viewer.isDestroyed()) { quitRequested = true; viewer.close(); }
  else finishQuit();
});
