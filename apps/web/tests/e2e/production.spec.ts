import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

test('production uses local assets, restrictive CSP and no demo even with query flag', async ({ page }) => {
  const errors: string[] = [], external: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:4173/') && !request.url().startsWith('data:')) external.push(request.url()); });
  await page.goto('/?demo=1');
  await expect(page.getByRole('heading', {name:'Войти в рабочее пространство'})).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => document.fonts.load('400 15px "Open Sans"', 'Проверка Қазақ'));
  expect(await page.evaluate(() => document.fonts.check('400 15px "Open Sans"', 'Проверка Қазақ'))).toBe(true);
  expect(await page.evaluate(() => Array.from(document.fonts).some(font => font.family.includes('Open Sans') && font.status === 'loaded'))).toBe(true);
  await expect(page.locator('body')).toHaveCSS('font-family', /Open Sans/);
  await expect(page.getByRole('button', {name:'Открыть синтетическое демо'})).toHaveCount(0);
  await page.getByRole('button', {name:'English',exact:true}).click();
  await expect(page.getByRole('heading', {name:'Enter your workspace'})).toBeVisible();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('button', {name:'Open synthetic demo'})).toHaveCount(0);
  expect(await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content')).not.toContain('unsafe-eval');
  expect(external).toEqual([]); expect(errors).toEqual([]);
});
test('production rejects a synthetic response from a configured server', async ({ page }) => {
  const data = JSON.parse(readFileSync('packages/contracts/fixtures/ui-positive.json', 'utf8'));
  await page.route(/\/api\/ui\/cases$/, route => route.fulfill({json:{items:[]}}));
  await page.route(/\/api\/ui\/cases\/synthetic-positive$/, route => route.fulfill({json:data}));
  await page.route('**/health/ready', route => route.fulfill({json:{ready:true,mode:'server',contract_version:'1.0.0'}}));
  await page.goto('/#case=synthetic-positive');
  await page.getByLabel('Ключ доступа',{exact:true}).fill('synthetic-production-test-key');
  await page.getByRole('button',{name:'Открыть рабочее пространство'}).click();
  await expect(page.getByRole('alert')).toContainText('синтетический пример');
  await expect(page.getByRole('heading',{name:'Обнаружены признаки возможных нарушений'})).toHaveCount(0);
});

test('synthetic lab computes all eight recorded cases locally without cloud or jury API requests', async ({ page }) => {
  const requests: string[] = [], errors: string[] = [];
  page.on('request', request => requests.push(request.url()));
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#synthetic-lab');
  await page.getByRole('button', {name:'Записанные примеры',exact:true}).click();
  await expect(page.getByRole('heading', { name: 'От наблюдения к точному моменту' })).toBeVisible();
  const cases = [
    ['01 Старт рядом с линией', ['1.5 с']], ['02 Пересечение слева направо', ['3.0 с']],
    ['03 Обратное направление', []], ['04 Повторные пересечения', ['2.0 с', '8.0 с']],
    ['05 Раннее событие', ['1.0 с']], ['06 Позднее событие', ['5.0 с']],
    ['07 Движение без пересечения', []], ['08 Неподвижный объект у линии', []],
  ] as const;
  for (const [name, times] of cases) {
    await page.getByRole('button', { name, exact: true }).click();
    await page.getByRole('button', { name: 'Проверить геометрию в браузере', exact: true }).click();
    await expect(page.getByText('Проверка пройдена', { exact: false })).toBeVisible();
    expect(await page.locator('.lab-local-result button').allTextContents()).toEqual([...times]);
    if (name.startsWith('01')) {
      const pending = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Скачать отчёт' }).click();
      const download = await pending;
      const report = JSON.parse(readFileSync((await download.path())!, 'utf8'));
      expect(report.raw_gemini_event_times_sec).toEqual([]);
      expect(report.browser_event_times_sec).toEqual([1.5]);
      expect(report.fresh_cloud_requests).toBe(0);
    }
  }
  await page.getByRole('button', { name: 'English', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'From observation to an exact moment' })).toBeVisible();
  expect(requests.filter(url => !url.startsWith('http://127.0.0.1:4173/') || url.includes('/api/'))).toEqual([]);
  expect(errors).toEqual([]);
});

test('cloud laboratory uses same-origin authenticated API and preserves the model result', async ({ page }) => {
  const seen: string[] = [], errors: string[] = [];
  page.on('request', request => seen.push(request.url()));
  page.on('pageerror', error => errors.push(error.message));
  const health = {synthetic_only:true, recorded_replay_ready:true, gemini_live_ready:true, gemini_block_reason:null, model:'gemini-3.1-flash-lite', live_requests_started_this_instance:0, max_live_requests_this_instance:8, results_ephemeral:true};
  await page.route('**/api/synthetic/session', route => {
    const ok = route.request().headers()['x-api-key'] === 'test-cloud-key';
    return route.fulfill({status:ok ? 200 : 401,json:ok ? health : {detail:'Invalid key'}});
  });
  await page.route('**/api/synthetic/jobs', async route => {
    expect(route.request().headers()['x-api-key']).toBe('test-cloud-key');
    expect(route.request().postDataJSON()).toEqual({scenario:'near_line_start',engine:'gemini'});
    await route.fulfill({status:202,json:{job_id:'abcd-1234'}});
  });
  const sourceHash = JSON.parse(readFileSync('apps/web/public/synthetic-demo/recordings.json','utf8')).cases[0].video_sha256;
  await page.route('**/api/synthetic/jobs/abcd-1234', route => route.fulfill({json:{job_id:'abcd-1234',status:'done',scenario:'near_line_start',engine:'gemini',elapsed_sec:4.2,result:{synthetic_only:true,new_gemini_requests:2,prompt_version:'native-reference-v12-review',model_version:'gemini-3.8-flash',raw_gemini_result:{event_times_sec:[1.5]},geometry_result:{event_times_sec:[2]},source_sha256:sourceHash,model_input_transform:{method:'static_red_reference_overlay'}}}}));
  await page.goto('/#synthetic-lab');
  await page.getByLabel('Ключ облачной лаборатории',{exact:true}).fill('wrong-key');
  await page.getByRole('button',{name:'Подключить Render',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Ключ лаборатории не принят');
  await page.getByLabel('Ключ облачной лаборатории',{exact:true}).fill('test-cloud-key');
  await page.getByRole('button',{name:'Подключить Render',exact:true}).click();
  await expect(page.getByText('Render подключён',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Новый анализ Gemini',exact:true}).click();
  await expect(page.getByTestId('cloud-model-times')).toHaveText('1.5 с');
  await expect(page.getByText('В синтетическом входе усилена видимость', {exact:false})).toBeVisible();
  const pending = page.waitForEvent('download');
  await page.getByRole('button',{name:'Скачать облачный JSON',exact:true}).click();
  const report = JSON.parse(readFileSync((await (await pending).path())!, 'utf8'));
  expect(report.result.raw_gemini_result.event_times_sec).toEqual([1.5]);
  expect(report.result.geometry_result.event_times_sec).toEqual([2]);
  expect(report.result.new_gemini_requests).toBe(2);
  expect(await page.evaluate(() => JSON.stringify({...localStorage}))).not.toContain('test-cloud-key');
  expect(await page.evaluate(() => JSON.stringify({...sessionStorage}))).not.toContain('test-cloud-key');
  expect(page.url()).not.toContain('test-cloud-key');
  expect(seen.every(url => url.startsWith('http://127.0.0.1:4173/'))).toBe(true);
  expect(seen.some(url => url.includes('/api/v1/') || url.includes('/api/ui/'))).toBe(false);
  expect(errors).toEqual([]);
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.getByRole('heading',{name:'New Gemini model response',exact:true})).toBeVisible();
});

test('cloud laboratory blocks live calls after expiry and reports a lost job as a failure', async ({ page }) => {
  const engines: string[] = [];
  await page.route('**/api/synthetic/session', route => route.fulfill({json:{synthetic_only:true,recorded_replay_ready:true,gemini_live_ready:false,gemini_block_reason:'EXPIRED',model:'gemini-3.1-flash-lite'}}));
  await page.route('**/api/synthetic/jobs', route => { engines.push(route.request().postDataJSON().engine); return route.fulfill({status:202,json:{job_id:'aaaa-1111'}}); });
  await page.route('**/api/synthetic/jobs/aaaa-1111', route => route.fulfill({status:410,json:{detail:'Lost after restart'}}));
  await page.goto('/#synthetic-lab');
  await page.getByLabel('Ключ облачной лаборатории',{exact:true}).fill('test-cloud-key');
  await page.getByRole('button',{name:'Подключить Render',exact:true}).click();
  await expect(page.getByRole('button',{name:'Новый анализ Gemini',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Запись + расчёт на Render',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Задание утрачено');
  await expect(page.getByTestId('cloud-model-times')).toHaveCount(0);
  expect(engines).toEqual(['recorded']);
});
