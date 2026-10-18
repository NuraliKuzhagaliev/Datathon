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
