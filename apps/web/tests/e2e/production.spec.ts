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
