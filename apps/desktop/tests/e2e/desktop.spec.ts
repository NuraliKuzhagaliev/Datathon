import { test, expect, _electron as electron } from '@playwright/test';
import path from 'node:path';
import { existsSync, mkdirSync, copyFileSync, writeFileSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';

test('Electron launcher, missing bundle, connected mode and sandboxed bridge', async () => {
  const server = createServer((_request, response) => { response.writeHead(200, {'Content-Type':'text/html'}); response.end('<!doctype html><html lang="ru"><head><title>Synthetic desktop smoke</title></head><body><h1>Synthetic test server</h1></body></html>'); });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address(); if (!address || typeof address === 'string') throw new Error('No test port');
  const app = await electron.launch({ args: [path.resolve('apps/desktop')], env: {...process.env, ELECTRON_DISABLE_SECURITY_WARNINGS:'false'} });
  try {
    const launcher = await app.firstWindow(); await expect(launcher.getByRole('heading',{name:'Где выполняется анализ?'})).toBeVisible();
    expect(await launcher.evaluate(() => typeof (window as any).require)).toBe('undefined');
    await launcher.screenshot({path:'apps/desktop/dist/qa-launcher.png'});
    if (!existsSync('releases/backend/launch.json')) {
      await launcher.locator('#local').click(); await expect(launcher.getByRole('status')).toContainText('сервис анализа не установлен');
    }
    await launcher.getByLabel('Адрес сервера').fill(`http://127.0.0.1:${address.port}`);
    const opened = app.waitForEvent('window'); await launcher.getByRole('button',{name:'Подключиться'}).click();
    const viewer = await opened; await expect(viewer.getByRole('heading',{name:'Synthetic test server'})).toBeVisible();
    expect(await viewer.evaluate(() => typeof (window as any).require)).toBe('undefined');
    const config = await viewer.evaluate(() => (window as any).cashproof.getConfig());
    expect(config).toEqual({mode:'connected',apiKey:null,contractVersion:'1.0.0'});
    const policy = await app.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows().map(w => ({ sandbox:w.webContents.getLastWebPreferences().sandbox, contextIsolation:w.webContents.getLastWebPreferences().contextIsolation, nodeIntegration:w.webContents.getLastWebPreferences().nodeIntegration })));
    for (const p of policy) expect(p).toEqual({sandbox:true,contextIsolation:true,nodeIntegration:false});
    const closed = viewer.waitForEvent('close');
    await viewer.evaluate(() => { setTimeout(() => { void (window as any).cashproof.showLauncher(); }, 50); });
    await closed; await expect(launcher.getByRole('heading',{name:'Где выполняется анализ?'})).toBeVisible();
  } finally { await app.close(); await new Promise<void>(resolve => server.close(() => resolve())); }
});

test('synthetic local process handshake, Unicode paths, in-memory key and shutdown', async () => {
  const root = path.resolve('apps/desktop/dist/Проверка runtime с пробелами'); const backend = path.join(root, 'backend');
  mkdirSync(backend, {recursive:true});
  copyFileSync(process.execPath, path.join(backend, 'node.exe'));
  copyFileSync('apps/desktop/tests/fake-backend.cjs', path.join(backend, 'fake-backend.cjs'));
  writeFileSync(path.join(backend,'launch.json'),JSON.stringify({contract_version:'1.0.0',executable:'node.exe',args_prefix:['fake-backend.cjs'],cwd:'.',env:{}}));
  const app = await electron.launch({args:[path.resolve('apps/desktop')],env:{...process.env,CASHPROOF_DESKTOP_TEST:'1',CASHPROOF_DESKTOP_TEST_ROOT:root}});
  let url = ''; let exited = false;
  try {
    const launcher = await app.firstWindow();
    const opened = app.waitForEvent('window'); await launcher.locator('#local').click();
    const viewer = await opened;
    await expect(viewer.getByRole('heading',{name:'Проверка операций'})).toBeVisible();
    await expect(viewer.getByText('Локальный сервис готов',{exact:true})).toBeVisible();
    url = new URL(viewer.url()).origin;
    const config = await viewer.evaluate(() => (window as any).cashproof.getConfig());
    expect(config.mode).toBe('offline'); expect(config.apiKey.length).toBe(64);
    expect(await viewer.evaluate(() => localStorage.length)).toBe(0);
    await expect(viewer.getByText('Первое дело начинается с видео',{exact:true})).toBeVisible();
    await viewer.getByRole('button',{name:'English',exact:true}).click();
    await expect(viewer.getByRole('heading',{name:'Operation review'})).toBeVisible();
    await viewer.reload();
    await expect(viewer.getByRole('heading',{name:'Operation review'})).toBeVisible();
    expect(await viewer.evaluate(() => JSON.stringify(localStorage))).toBe('{"cashproof.language":"en"}');
    await viewer.getByRole('button',{name:'Русский',exact:true}).click();
    await viewer.screenshot({path:'apps/desktop/dist/qa-local-synthetic.png'});
    // Stub the native choice only in this test; exercise the real unload and
    // quit handlers, retaining the synthetic owned backend when the user stays.
    await app.evaluate(({dialog}) => {
      (globalThis as any).discardDraft = false; (globalThis as any).unloadPrompts = 0;
      dialog.showMessageBoxSync = () => { (globalThis as any).unloadPrompts++; return (globalThis as any).discardDraft ? 1 : 0; };
    });
    await viewer.evaluate(() => window.addEventListener('beforeunload', event => { event.preventDefault(); event.returnValue = ''; }));
    await app.evaluate(({app}) => app.quit());
    await expect.poll(() => app.evaluate(() => (globalThis as any).unloadPrompts)).toBe(1);
    expect(viewer.isClosed()).toBe(false);
    expect((await fetch(`${url}/health/ready`)).ok).toBe(true);
    await viewer.evaluate(() => (window as any).cashproof.showLauncher());
    await expect.poll(() => app.evaluate(() => (globalThis as any).unloadPrompts)).toBe(2);
    expect(viewer.isClosed()).toBe(false);
    expect((await fetch(`${url}/health/ready`)).ok).toBe(true);
    const closed = app.waitForEvent('close');
    await app.evaluate(({app}) => { (globalThis as any).discardDraft = true; setTimeout(() => app.quit(), 50); });
    await closed; exited = true;
  } finally { if (!exited) await app.close(); }
  await expect.poll(async () => { try { await fetch(`${url}/health/ready`,{signal:AbortSignal.timeout(1000)}); return false; } catch { return true; } }).toBeTruthy();
});

test('packaged connected EXE starts and refuses missing offline resources', async () => {
  const exe = path.resolve(process.env.CASHPROOF_PACKAGED_EXE || 'apps/desktop/dist/connected/win-unpacked/CashProof Connected.exe');
  test.skip(!existsSync(exe), 'Build the connected Windows folder before this check.');
  const app = await electron.launch({executablePath:exe,args:[]});
  try {
    const launcher = await app.firstWindow(); await expect(launcher.getByRole('heading',{name:'Где выполняется анализ?'})).toBeVisible();
    expect(await app.evaluate(({app})=>app.isPackaged)).toBeTruthy();
    if (process.env.CASHPROOF_PACKAGED_EXE) {
      const folder = path.dirname(exe);
      expect(readFileSync(path.join(folder, 'resources/web/third-party-notices.txt'), 'utf8')).toContain('react 19.3.1');
      expect(existsSync(path.join(folder, 'LICENSE.electron.txt'))).toBeTruthy();
      expect(existsSync(path.join(folder, 'LICENSES.chromium.html'))).toBeTruthy();
    }
    await launcher.locator('#local').click(); await expect(launcher.getByRole('status')).toContainText('сервис анализа не установлен');
    await launcher.screenshot({path:'apps/desktop/dist/qa-packaged.png'});
  } finally { await app.close(); }
});

test('incompatible local API fails promptly instead of waiting for model timeout', async () => {
  const root = path.resolve('apps/desktop/dist/incompatible-runtime'); const backend = path.join(root,'backend');
  mkdirSync(backend,{recursive:true});
  copyFileSync(process.execPath,path.join(backend,'node.exe'));
  copyFileSync('apps/desktop/tests/fake-backend.cjs',path.join(backend,'fake-backend.cjs'));
  writeFileSync(path.join(backend,'launch.json'),JSON.stringify({contract_version:'1.0.0',executable:'node.exe',args_prefix:['fake-backend.cjs'],cwd:'.',env:{CASHPROOF_TEST_HEALTH_VERSION:'2.0.0'}}));
  const app = await electron.launch({args:[path.resolve('apps/desktop')],env:{...process.env,CASHPROOF_DESKTOP_TEST:'1',CASHPROOF_DESKTOP_TEST_ROOT:root}});
  try {
    const launcher = await app.firstWindow();
    await launcher.locator('#local').click();
    await expect(launcher.getByRole('status')).toContainText('Несовместимая версия', {timeout:10000});
    await expect(launcher.locator('#local')).toBeEnabled();
  } finally { await app.close(); }
});
