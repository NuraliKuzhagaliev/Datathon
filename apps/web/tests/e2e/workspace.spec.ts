import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const fixture = (name: string) => JSON.parse(readFileSync(`packages/contracts/fixtures/${name}.json`, 'utf8'));

test('Russian quick start can collapse, reopen and navigate to a marked demo', async ({ page }) => {
  await page.goto('/?demo=1');
  await expect(page.getByRole('heading', {name:'Четыре шага проверки'})).toBeVisible();
  await expect(page.locator('.quick-start-steps li')).toHaveCount(4);
  await expect(page.getByText('Загрузите видео', {exact:true})).toBeVisible();
  await expect(page.locator('body')).not.toContainText('Synthetic demo');
  await expect(page.locator('body')).not.toContainText('Evidence workspace');
  await page.getByRole('button',{name:'Свернуть инструкцию'}).click();
  await expect(page.locator('#quick-start-steps')).not.toBeVisible();
  await page.getByRole('button',{name:'Библиотека норм',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Учебное основание'})).toBeVisible();
  await page.getByRole('button',{name:'Дела',exact:true}).click();
  await expect(page.locator('#quick-start-steps')).not.toBeVisible();
  await page.getByRole('button',{name:'Как начать'}).click();
  await page.screenshot({path:'apps/web/dist/qa-guide.png',fullPage:true});
  await page.getByRole('button',{name:'Разобрать демопример'}).click();
  await expect(page.getByRole('heading',{name:'Учебное событие 1',exact:true})).toBeVisible();
  await expect(page.getByText('Синтетическое демо',{exact:true})).toBeVisible();
});

test('focus mode preserves note, supports shortcuts and exits dialogs before changing layout', async ({ page }) => {
  await page.goto('/?demo=1#case=synthetic-positive');
  await expect(page.getByRole('heading',{name:'Учебное событие 1',exact:true})).toBeVisible();
  const normal = await page.locator('.evidence-stage').boundingBox();
  await page.getByText('Заметка проверяющего · добавить',{exact:true}).click();
  await page.getByLabel('Заметка',{exact:true}).fill('Несохранённый учебный текст');
  await page.getByRole('button',{name:'Сосредоточенная проверка',exact:true}).click();
  await expect(page.locator('.sidebar')).not.toBeVisible();
  await expect(page.getByRole('button',{name:'Обычный вид',exact:true})).toHaveAttribute('aria-pressed','true');
  const focused = await page.locator('.evidence-stage').boundingBox();
  expect(focused!.width).toBeGreaterThan(normal!.width);
  expect(focused!.height).toBeGreaterThan(normal!.height);
  await expect(page.getByLabel('Заметка',{exact:true})).toHaveValue('Несохранённый учебный текст');
  await page.getByLabel('Заметка',{exact:true}).press('f');
  await expect(page.locator('.app-shell')).toHaveClass(/focus-mode/);
  await page.getByRole('button',{name:'Горячие клавиши',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('j');
  await expect(page.getByRole('heading',{name:'Учебное событие 1',exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.locator('.app-shell')).toHaveClass(/focus-mode/);
  await page.screenshot({path:'apps/web/dist/qa-focus-1366.png',fullPage:true});
  await page.keyboard.press('Escape');
  await expect(page.locator('.sidebar')).toBeVisible();
  await expect(page.getByRole('button',{name:'Сосредоточенная проверка',exact:true})).toBeFocused();
  await page.keyboard.press('j');
  await expect(page.getByRole('heading',{name:'Учебное событие 2',exact:true})).toBeVisible();
  await page.keyboard.press('k');
  await expect(page.getByRole('heading',{name:'Учебное событие 1',exact:true})).toBeVisible();
  await page.keyboard.press('f');
  await expect(page.locator('.app-shell')).toHaveClass(/focus-mode/);
  await page.getByRole('button',{name:'Все дела',exact:true}).click();
  await expect(page.locator('.sidebar')).toBeVisible();
});

for (const width of [1024, 390]) test(`focus and guidance stay within ${width}px`, async ({ page }) => {
  await page.setViewportSize({width,height:844});
  await page.goto('/?demo=1');
  await expect(page.locator('.quick-start')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Разобрать демопример'}).click();
  await page.getByRole('button',{name:'Сосредоточенная проверка',exact:true}).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator('.sidebar')).not.toBeVisible();
  const save = await page.getByRole('button',{name:'Сохранить решение'}).boundingBox();
  expect(save!.x + save!.width).toBeLessThanOrEqual(width);
  await page.screenshot({path:`apps/web/dist/qa-focus-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:'Обычный вид',exact:true}).click();
  await expect(page.locator('.sidebar')).toBeVisible();
});

test('synthetic multi-event review, rule source, keyboard, export error', async ({ page }) => {
  await page.goto('/?demo=1');
  await page.getByRole('button', { name: 'Открыть дело synthetic-positive', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Обнаружены признаки возможных нарушений' })).toBeVisible();
  await expect(page.getByText('Синтетическое демо', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Следующее событие' }).click();
  await expect(page.getByRole('heading', { name: 'Учебное событие 2', exact: true })).toBeVisible();
  await page.keyboard.press('k');
  await expect(page.getByRole('heading', { name: 'Учебное событие 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
  await page.getByText('Заметка проверяющего · добавить', { exact: true }).click();
  await page.getByLabel('Заметка', { exact: true }).fill('Synthetic UI review only');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Сохранено в памяти демо. Исходный результат не изменён.')).toBeVisible();
  await page.getByRole('button', { name: /ОСНОВАНИЕ/ }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('Не применяется', { exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: 'Экспорт дела' }).click();
  await expect(page.getByText(/Демо не содержит видео или настоящего ZIP/)).toBeVisible();
  await page.screenshot({ path: 'apps/web/dist/qa-evidence-1366.png', fullPage: true });
});

for (const viewport of [{width:1440,height:900},{width:1366,height:768},{width:1024,height:768},{width:390,height:844}]) {
  test(`responsive evidence ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport); await page.goto('/?demo=1#case=synthetic-positive');
    await expect(page.getByRole('heading', { name: 'Учебное событие 1', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    const image = page.getByAltText('Доказательство события 1, 00:12.4'); await expect(image).toBeVisible();
    await expect(image).toHaveCSS('object-fit', 'contain');
    const stage = await page.locator('.evidence-stage').boundingBox();
    expect(stage!.x + stage!.width).toBeLessThanOrEqual(viewport.width);
    const save = await page.getByRole('button', { name: 'Сохранить решение' }).boundingBox();
    expect(save!.x + save!.width).toBeLessThanOrEqual(viewport.width);
    if (viewport.width >= 1101) {
      const panel = await page.locator('.desk').boundingBox();
      const storyboard = await page.locator('.storyboard').boundingBox();
      expect(storyboard!.y + storyboard!.height).toBeLessThanOrEqual(panel!.y + panel!.height);
    }
    await page.screenshot({ path: `apps/web/dist/qa-evidence-${viewport.width}.png`, fullPage: true });
  });
}
test('negative, processing, failed, rules, upload and system states', async ({ page }) => {
  await page.goto('/?demo=1#case=synthetic-negative'); await expect(page.getByRole('heading', { name: 'Нарушение не обнаружено', exact: true }).first()).toBeVisible();
  await page.screenshot({ path: 'apps/web/dist/qa-negative.png', fullPage: true });
  await page.goto('/?demo=1#case=synthetic-processing'); await expect(page.getByRole('heading', { name: 'Просмотр видеоряда', exact: true }).first()).toBeVisible();
  await expect(page.getByText('Процент этапа пока неизвестен')).toBeVisible();
  await page.screenshot({ path: 'apps/web/dist/qa-processing.png', fullPage: true });
  await page.goto('/?demo=1#case=synthetic-failed'); await expect(page.getByRole('heading', { name: 'Анализ не завершён' })).toBeVisible();
  await page.getByRole('button', { name: 'Загрузить другое видео' }).click(); await expect(page.getByText(/В синтетическом демо загрузка отключена/)).toBeVisible(); await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Библиотека норм', exact: true }).click(); await expect(page.getByRole('heading', { name: 'Библиотека норм' })).toBeVisible();
  await page.getByRole('button', { name: 'Система', exact: true }).click(); await expect(page.getByRole('heading', { name: 'Сервис анализа' })).toBeVisible();
});

test('major screens and keyboard focus with synthetic fixtures', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/'); await page.screenshot({path:'apps/web/dist/qa-connect.png',fullPage:true});
  await page.keyboard.press('Tab'); await expect(page.getByRole('link',{name:'Перейти к содержимому'})).toBeFocused();
  await page.getByRole('button',{name:'Открыть синтетическое демо'}).click();
  await expect(page.getByRole('heading',{name:'Проверка операций'})).toBeVisible();
  await page.screenshot({path:'apps/web/dist/qa-cases.png',fullPage:true});
  await page.getByRole('button',{name:'Новый анализ',exact:true}).click();
  await page.screenshot({path:'apps/web/dist/qa-upload.png',fullPage:true});
  await page.keyboard.press('Escape'); await expect(page.getByRole('button',{name:'Новый анализ',exact:true})).toBeFocused();
  await page.getByRole('button',{name:'Библиотека норм',exact:true}).click(); await expect(page.getByRole('heading',{name:'Учебное основание'})).toBeVisible();
  await page.screenshot({path:'apps/web/dist/qa-rules.png',fullPage:true});
  expect(errors).toEqual([]);
});
test('real client mock HTTP: auth, multipart upload, polling, complete negative; no real video', async ({ page }) => {
  let accepted = false; let polled = 0; const negative = fixture('ui-negative'); negative.is_synthetic = false; negative.job_id = 'http-test'; negative.model_result.job_id = 'http-test'; negative.filename = 'synthetic-upload.mov';
  const pending = fixture('ui-processing'); pending.is_synthetic = false; pending.job_id = 'http-test';
  await page.route(/\/api\/(?:ui|v1)\//, async route => {
    const request = route.request(); const url = new URL(request.url());
    if (request.headers()['x-api-key'] !== 'synthetic-test-key') { await route.fulfill({ status: 401, json: { error: { code:'UNAUTHORIZED', message:'Synthetic test' } } }); return; }
    if (url.pathname === '/api/ui/cases') { await route.fulfill({ json: { items: [] } }); return; }
    if (url.pathname === '/api/v1/analyze') { expect(request.headers()['content-type']).toContain('multipart/form-data'); expect(request.postDataBuffer()?.toString()).toContain('name="file"'); accepted = true; await route.fulfill({status:202,json:{job_id:'http-test'}}); return; }
    if (url.pathname === '/api/ui/cases/http-test') { polled++; await route.fulfill({json:polled === 1 ? pending : negative}); return; }
    await route.fulfill({status:404,json:{error:{code:'NOT_FOUND',message:'Synthetic test'}}});
  });
  await page.route('**/health/ready', route => route.fulfill({json:{ready:true,mode:'server',contract_version:'1.0.0'}}));
  await page.goto('/'); await page.getByLabel('Ключ доступа', { exact: true }).fill('wrong-key'); await page.getByRole('button', { name: 'Открыть рабочее пространство' }).click(); await expect(page.getByRole('alert')).toContainText('Ключ доступа не принят');
  await page.getByLabel('Ключ доступа', { exact: true }).fill('synthetic-test-key'); await page.getByRole('button', { name: 'Открыть рабочее пространство' }).click();
  await page.getByRole('button', { name: 'Новый анализ', exact: true }).click();
  await page.locator('input[type=file]').setInputFiles({name:'bad.txt',mimeType:'text/plain',buffer:Buffer.from('synthetic')}); await expect(page.getByRole('alert')).toContainText('MOV');
  await page.locator('input[type=file]').setInputFiles({name:'synthetic-upload.mov',mimeType:'video/quicktime',buffer:Buffer.from('synthetic test bytes, not a real video')});
  await page.getByRole('button', { name: 'Начать анализ', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Нарушение не обнаружено', exact: true }).first()).toBeVisible();
  expect(accepted).toBeTruthy(); expect(polled).toBeGreaterThan(1);
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('synthetic-test-key');
});

test('mock HTTP media mapping, review errors, export and Blob cleanup with generated video', async ({ page }) => {
  // These transport fixtures exercise the real client. All pixels and observations
  // are synthetic; toggling flags here is not an inference or integration result.
  const positive = fixture('ui-positive'); positive.is_synthetic = false; positive.media_ready = true;
  positive.rules[0].enabled = true;
  positive.time_map = [{source_start_sec:0,source_end_sec:30,preview_start_sec:0,preview_end_sec:15}];
  let failReview = true;
  await page.addInitScript(() => { const revoke = URL.revokeObjectURL; (window as any).revoked = 0; URL.revokeObjectURL = url => { (window as any).revoked++; revoke(url); }; });
  await page.route(/\/api\/(?:ui|v1)\//, async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/ui/cases') { await route.fulfill({json:{items:[]}}); return; }
    if (url.pathname.endsWith('/media')) { await route.fulfill({contentType:'video/mp4',body:Buffer.from(readFileSync('apps/web/tests/assets/synthetic-preview.base64.txt','utf8'),'base64')}); return; }
    if (url.pathname.includes('/reviews/')) {
      if (failReview) { failReview = false; await route.fulfill({status:503,json:{error:{code:'UNAVAILABLE',message:'Synthetic test'}}}); }
      else { await route.fulfill({json:{...route.request().postDataJSON(),event_id:'synthetic-event-1',updated_at:new Date().toISOString()}}); }
      return;
    }
    if (url.pathname.endsWith('/bundle')) { await route.fulfill({contentType:'application/zip',body:Buffer.from('504b0506000000000000000000000000000000000000','hex')}); return; }
    await route.fulfill({json:positive});
  });
  await page.route('**/health/ready', route => route.fulfill({json:{ready:true,mode:'server',contract_version:'1.0.0'}}));
  await page.goto('/#case=synthetic-positive'); await page.getByLabel('Ключ доступа', {exact:true}).fill('synthetic-test-key'); await page.getByRole('button',{name:'Открыть рабочее пространство'}).click();
  const media = page.locator('video'); await expect.poll(() => media.evaluate((v: HTMLVideoElement) => v.readyState)).toBeGreaterThan(0);
  await page.getByRole('button', {name:'Видео',exact:true}).click();
  await expect.poll(() => media.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeCloseTo(6.2,1);
  await media.evaluate((v: HTMLVideoElement) => v.dataset.viewCheck = 'same-player');
  await page.getByRole('button',{name:'Сосредоточенная проверка',exact:true}).click();
  await expect(media).toHaveAttribute('data-view-check','same-player');
  await expect.poll(() => media.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeCloseTo(6.2,1);
  await page.getByRole('button',{name:'Обычный вид',exact:true}).click();
  await page.getByRole('button',{name:'Следующее событие'}).click(); await page.getByRole('button',{name:'Видео',exact:true}).click();
  await expect.poll(() => media.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeCloseTo(10.5,1);
  await page.getByRole('button',{name:'Контекст',exact:true}).click();
  await expect(page.getByRole('button',{name:'Повтор включён',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Пауза',exact:true}).click();
  await page.getByRole('button',{name:'Предыдущее событие'}).click();
  await page.getByRole('button',{name:'Сохранить решение'}).click(); await expect(page.getByRole('alert')).toContainText('не готовы');
  await page.getByRole('button',{name:'Сохранить решение'}).click(); await expect(page.getByText('Решение сохранено. Исходный результат модели не изменён.')).toBeVisible();
  const download = page.waitForEvent('download'); await page.getByRole('button',{name:'Экспорт дела'}).click(); expect((await download).suggestedFilename()).toBe('cashproof-synthetic-positive.zip');
  await page.getByRole('button',{name:'Все дела',exact:true}).click();
  await expect.poll(() => page.evaluate(() => (window as any).revoked)).toBeGreaterThan(0);
});
