import { test, expect } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdtempSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { tmpdir } from 'node:os';

const python = path.resolve(process.env.CASHPROOF_TEST_PYTHON || '.tools/integration-venv/Scripts/python.exe');
const backend = path.resolve(process.env.CASHPROOF_BACKEND_ROOT || '.tools/backend-reference');
const key = randomBytes(32).toString('hex'), juryKey = randomBytes(32).toString('hex');

async function start(scenario: string) {
  const data = mkdtempSync(path.join(tmpdir(), 'cashproof-synthetic-integration-'));
  const child = spawn(python, ['apps/web/tests/integration/server.py', '--backend', backend, '--frontend', path.resolve('apps/web/dist'), '--data', data, '--scenario', scenario], {
    windowsHide: true, env: {...process.env, PYTHONUNBUFFERED:'1', CASHPROOF_TEST_KEY:key, CASHPROOF_TEST_JURY_KEY:juryKey}, stdio:['ignore','pipe','pipe'],
  });
  const ready = await new Promise<{port: number; clip: string}>((resolve, reject) => {
    let buffer = '', diagnostics = '';
    const timeout = setTimeout(() => reject(new Error(`Synthetic integration startup timed out: ${diagnostics}`)), 30000);
    child.stderr!.on('data', chunk => { diagnostics = (diagnostics + chunk.toString()).slice(-4000); });
    child.once('error', error => { clearTimeout(timeout); reject(error); });
    child.once('exit', code => { clearTimeout(timeout); reject(new Error(`Synthetic test server exited (${code}): ${diagnostics}`)); });
    child.stdout!.on('data', chunk => {
      buffer += chunk.toString();
      let end;
      while ((end = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, end); buffer = buffer.slice(end + 1);
        try { const message = JSON.parse(line); if (message.event === 'synthetic_integration_ready') { clearTimeout(timeout); resolve(message); } } catch { /* Ignore non-protocol test output. */ }
      }
    });
  }).catch(async error => { await stop(child); throw error; });
  return {child, origin:`http://127.0.0.1:${ready.port}`, clip:ready.clip};
}
async function stop(child: ChildProcess) {
  if (child.exitCode !== null || !child.pid) return;
  if (process.platform === 'win32') await new Promise<void>(resolve => {
    const killer = spawn(path.join(process.env.SystemRoot || 'C:\\Windows','System32/taskkill.exe'), ['/PID',String(child.pid),'/T','/F'], {windowsHide:true,stdio:'ignore'});
    killer.once('exit', () => resolve()); killer.once('error', () => { child.kill(); resolve(); });
  }); else child.kill('SIGTERM');
}

for (const scenario of ['positive','negative','failed']) test(`A FastAPI + B production UI: ${scenario} synthetic pipeline`, async ({page, request}) => {
  const server = await start(scenario);
  try {
    const headers = {'X-API-Key':key};
    expect((await request.get(`${server.origin}/api/ui/cases`)).status()).toBe(401);
    expect((await request.get(`${server.origin}/api/ui/cases`,{headers:{'X-API-Key':juryKey}})).status()).toBe(401);
    await page.goto(server.origin);
    await page.getByRole('button',{name:'English',exact:true}).click();
    await page.getByLabel('Access key',{exact:true}).fill(key);
    await page.getByRole('button',{name:'Open workspace',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Operation review',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'New analysis',exact:true}).click();
    await page.locator('input[type=file]').setInputFiles(server.clip);
    await page.getByRole('button',{name:'Start analysis',exact:true}).click();
    await expect(page.locator('.state-card')).toBeVisible();
    const heading = scenario === 'positive' ? 'Signs of possible violations detected' : scenario === 'negative' ? 'No violation detected' : 'Analysis did not finish';
    await expect(page.getByRole('heading',{name:heading,exact:true}).first()).toBeVisible({timeout:60000});
    const job = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('case')!;
    const getResult = async () => (await request.get(`${server.origin}/api/v1/jobs/${job}`,{headers})).json();
    const original = await getResult();
    if (scenario === 'failed') {
      expect(original.status).toBe('failed'); expect(original).not.toHaveProperty('verdict');
      await expect(page.getByRole('button',{name:'Export case',exact:true})).toBeDisabled();
    } else {
      expect(original.verdict).toBe(scenario === 'positive' ? 'violation' : 'no_violation');
      if (scenario === 'positive') {
        await expect(page.locator('.event-card')).toHaveCount(2);
        await expect(page.locator('.original-frame')).toBeVisible();
        await expect(page.getByRole('button',{name:'Video',exact:true})).toBeEnabled({timeout:30000});
        await page.getByRole('button',{name:'Video',exact:true}).click();
        await expect.poll(() => page.locator('video').evaluate((v:HTMLVideoElement)=>v.readyState)).toBeGreaterThan(0);
        await page.getByRole('button',{name:/RULE SOURCE/}).click();
        await expect(page.getByRole('dialog')).toContainText('Synthetic test only');
        await page.getByRole('button',{name:'Close',exact:true}).click();
        await page.getByRole('button',{name:'Dismiss',exact:true}).click();
        await page.getByText('Reviewer note · add',{exact:true}).click();
        await page.getByLabel('Note',{exact:true}).fill('Synthetic integration review — unchanged source result.');
        await page.getByRole('button',{name:'Save decision',exact:true}).click();
        await expect(page.locator('.save-message')).toContainText('Decision saved.');
        expect(await getResult()).toEqual(original);
        await page.reload();
        await page.getByLabel('Access key',{exact:true}).fill(key);
        await page.getByRole('button',{name:'Open workspace',exact:true}).click();
        await expect(page.getByRole('button',{name:'Dismiss',exact:true})).toHaveAttribute('aria-pressed','true');
        await page.getByText('Reviewer note · added',{exact:true}).click();
        await expect(page.getByLabel('Note',{exact:true})).toHaveValue('Synthetic integration review — unchanged source result.');
      } else expect(original.violations).toEqual([]);
      const downloadEvent = page.waitForEvent('download');
      await page.getByRole('button',{name:'Export case',exact:true}).click();
      const download = await downloadEvent;
      expect(download.suggestedFilename()).toBe(`cashproof-${job}.zip`);
      const zip = readFileSync((await download.path())!);
      expect(zip.subarray(0,2).toString()).toBe('PK');
      expect(zip.length).toBeGreaterThan(200);
    }
    expect((await request.get(`${server.origin}/api/v1/jobs/${job}`,{headers:{'X-API-Key':juryKey}})).status()).toBe(404);
    expect(await page.evaluate(()=>JSON.stringify(localStorage))).not.toContain(key);
    await page.getByRole('button',{name:'All cases',exact:true}).click();
    await page.getByRole('button',{name:`Delete case ${job}`,exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Delete case',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Your first case starts with a video'})).toBeVisible();
    expect((await request.get(`${server.origin}/api/v1/jobs/${job}`,{headers})).status()).toBe(404);
  } finally { await stop(server.child); }
});
