import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

test('language persists across reload, translates errors, and keeps access key out of storage', async ({ page }) => {
  await page.route('**/api/ui/cases', route => route.fulfill({status:401,json:{error:{code:'UNAUTHORIZED',message:'synthetic'}}}));
  await page.goto('/');
  await page.getByLabel('Ключ доступа', {exact:true}).fill('synthetic-language-key');
  await page.getByRole('button',{name:'Открыть рабочее пространство'}).click();
  await expect(page.getByRole('alert')).toContainText('Ключ доступа не принят');
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  await expect(page).toHaveTitle('CashProof — Operation review');
  await expect(page.getByLabel('Access key',{exact:true})).toHaveValue('synthetic-language-key');
  await expect(page.getByRole('alert')).toContainText('Access key not accepted');
  expect(await page.evaluate(() => JSON.stringify(localStorage))).toBe('{"cashproof.language":"en"}');
  await page.reload();
  await expect(page.getByRole('heading',{name:'Enter your workspace'})).toBeVisible();
  await expect(page.getByLabel('Access key',{exact:true})).toHaveValue('');
  await page.getByRole('button',{name:'Русский',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Войти в рабочее пространство'})).toBeVisible();
});

test('English demo includes guide, sources and states; switching retains event, review and note', async ({ page }) => {
  await page.goto('/?demo=1');
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Four steps to review'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Upload a video'})).toBeVisible();
  await page.getByRole('button',{name:'Explore demo case'}).click();
  await expect(page.getByRole('heading',{name:'Demo event 1',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Next event',exact:true}).click();
  await page.getByRole('button',{name:'Dismiss',exact:true}).click();
  await page.getByText('Reviewer note · add',{exact:true}).click();
  await page.getByLabel('Note',{exact:true}).fill('Original note / исходная заметка');
  await page.getByRole('button',{name:'Focus view',exact:true}).click();
  await page.getByRole('button',{name:'Русский',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Учебное событие 2',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Отклонить',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.getByLabel('Заметка',{exact:true})).toHaveValue('Original note / исходная заметка');
  await expect(page.locator('.app-shell')).toHaveClass(/focus-mode/);
  await page.getByRole('button',{name:'English',exact:true}).click();
  await page.getByRole('button',{name:'Save decision',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Saved in demo memory');
  await page.getByRole('button',{name:/RULE SOURCE/}).click();
  await expect(page.getByRole('dialog')).toContainText('Demo rule source');
  await expect(page.getByRole('dialog')).toContainText('Not applicable');
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.getByRole('button',{name:'Export case',exact:true}).click();
  await expect(page.locator('.notice[role=status]')).toContainText('The demo has no video or real ZIP');
  await page.getByRole('button',{name:'All cases',exact:true}).click();
  await page.getByLabel('Search cases').fill('no events');
  await page.getByRole('button',{name:'Open case synthetic-negative'}).click();
  await expect(page.getByRole('heading',{name:'No violation detected',exact:true}).first()).toBeVisible();
  await page.getByRole('button',{name:'Rule library',exact:true}).click();
  await page.getByLabel('Search rules').fill('Demo rule');
  await expect(page.getByRole('heading',{name:'Demo rule source'})).toBeVisible();
  await page.getByRole('button',{name:'System',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Analysis service'})).toBeVisible();
});

test('changing UI language preserves server evidence, legal text and review payload', async ({ page }) => {
  // Synthetic transport fixture only; this is not real case content.
  const data = JSON.parse(readFileSync('packages/contracts/fixtures/ui-positive.json','utf8'));
  data.is_synthetic = false; data.rules[0].enabled = true;
  data.filename = 'Учебное событие 1.mov';
  data.events[0].type = data.model_result.violations[0].type = 'Учебное событие 1';
  data.events[0].observation = 'Учебное событие 1';
  data.rules[0].display_name = 'Учебное основание';
  let saved: unknown;
  await page.route('**/health/ready', route => route.fulfill({json:{ready:true,mode:'server',contract_version:'1.0.0'}}));
  await page.route('**/api/ui/**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/cases')) { await route.fulfill({json:{items:[]}}); return; }
    if (url.pathname.includes('/reviews/')) {
      saved = route.request().postDataJSON();
      await route.fulfill({json:{...saved as object,event_id:data.events[0].event_id,updated_at:new Date().toISOString()}}); return;
    }
    await route.fulfill({json:data});
  });
  await page.goto('/#case=synthetic-positive');
  await page.getByLabel('Ключ доступа',{exact:true}).fill('synthetic-key');
  await page.getByRole('button',{name:'Открыть рабочее пространство'}).click();
  await expect(page.getByRole('heading',{name:'Учебное событие 1',exact:true})).toBeVisible();
  const image = await page.locator('.original-frame').getAttribute('src');
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Учебное событие 1',exact:true})).toBeVisible();
  await expect(page.locator('.filename')).toHaveText('Учебное событие 1.mov');
  await expect(page.locator('.source-card')).toContainText('Учебное основание');
  expect(await page.locator('.original-frame').getAttribute('src')).toBe(image);
  await page.getByRole('button',{name:'Confirm',exact:true}).click();
  await page.getByText('Reviewer note · add',{exact:true}).click();
  await page.getByLabel('Note',{exact:true}).fill('Учебное событие 1');
  await page.getByRole('button',{name:'Save decision',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Decision saved.');
  expect(saved).toEqual({decision:'confirmed',note:'Учебное событие 1'});
});

for (const width of [1366, 390]) test(`English layout fits ${width}px`, async ({ page }) => {
  await page.setViewportSize({width,height:900});
  await page.goto('/?demo=1');
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Operation review'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:`apps/web/dist/qa-english-cases-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:'Explore demo case'}).click();
  await expect(page.getByAltText('Evidence for event 1, 00:12.4')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:`apps/web/dist/qa-english-evidence-${width}.png`,fullPage:true});
  const english = await page.locator('.original-frame').getAttribute('src');
  await page.getByRole('button',{name:'Русский',exact:true}).click();
  expect(await page.locator('.original-frame').getAttribute('src')).not.toBe(english);
});

test('blocked storage does not prevent language switching', async ({ page }) => {
  await page.addInitScript(() => { Storage.prototype.getItem = () => { throw new DOMException('blocked','SecurityError'); }; Storage.prototype.setItem = () => { throw new DOMException('blocked','SecurityError'); }; });
  await page.goto('/');
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Enter your workspace'})).toBeVisible();
});
