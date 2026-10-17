import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

test('case overview filters real list metadata, sorts, searches IDs and fits mobile English', async ({ page }) => {
  const items = [
    {job_id:'test-positive',filename:'B.mov',created_at:'2026-10-17T10:00:00Z',status:'done',verdict:'violation'},
    {job_id:'test-negative',filename:'A.mov',created_at:'2026-10-17T11:00:00Z',status:'done',verdict:'no_violation'},
    {job_id:'test-failed',filename:'C.mov',created_at:'2026-10-17T12:00:00Z',status:'failed',verdict:null},
  ];
  await page.route('**/api/ui/cases', route => route.fulfill({json:{items}}));
  await page.route('**/health/ready', route => route.fulfill({json:{ready:true,mode:'server',contract_version:'1.0.0'}}));
  await page.goto('/');
  await page.getByLabel('Ключ доступа',{exact:true}).fill('synthetic-key');
  await page.getByRole('button',{name:'Открыть рабочее пространство'}).click();
  await expect(page.locator('.case-overview strong')).toHaveText(['3','1','0','1','1']);
  await expect(page.locator('.case-open strong')).toHaveText(['C.mov','A.mov','B.mov']);
  await page.getByLabel('Порядок дел').selectOption('oldest');
  await expect(page.locator('.case-open strong')).toHaveText(['B.mov','A.mov','C.mov']);
  await page.getByLabel('Порядок дел').selectOption('name');
  await expect(page.locator('.case-open strong')).toHaveText(['A.mov','B.mov','C.mov']);
  await page.getByRole('button',{name:'Ошибки обработки',exact:true}).click();
  await expect(page.locator('.case-open strong')).toHaveText(['C.mov']);
  await page.getByLabel('Поиск дел').fill('TEST-NEGATIVE');
  await expect(page.getByText('Подходящих дел нет',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Сбросить поиск и фильтр'}).click();
  await page.getByLabel('Поиск дел').fill(' TEST-NEGATIVE ');
  await expect(page.locator('.case-open strong')).toHaveText(['A.mov']);
  await page.getByRole('button',{name:'English',exact:true}).click();
  await page.getByRole('button',{name:'Clear search and filter'}).click();
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('button',{name:'Processing errors',exact:true})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:'apps/web/dist/qa-polish-cases-mobile.png',fullPage:true});
});

test('drafts survive event and case navigation, warn on exit, and display acknowledged review immediately', async ({ page }) => {
  await page.goto('/?demo=1#case=synthetic-positive');
  await page.getByText('Заметка проверяющего · добавить',{exact:true}).click();
  await page.getByLabel('Заметка',{exact:true}).fill('Synthetic private draft');
  await page.getByRole('button',{name:'Не уверен',exact:true}).click();
  await page.getByRole('button',{name:'Следующее событие'}).click();
  await expect(page.locator('.event-card').first()).toContainText('Есть несохранённый черновик');
  await page.getByRole('button',{name:'Все дела',exact:true}).click();
  await page.getByRole('button',{name:'Открыть дело synthetic-positive'}).click();
  await page.getByText('Заметка проверяющего · есть текст',{exact:true}).click();
  await expect(page.getByLabel('Заметка',{exact:true})).toHaveValue('Synthetic private draft');
  await expect(page.getByRole('button',{name:'Не уверен',exact:true})).toHaveAttribute('aria-pressed','true');
  expect(await page.evaluate(() => window.dispatchEvent(new Event('beforeunload',{cancelable:true})))).toBe(false);
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('Synthetic private draft');
  await page.getByRole('button',{name:'Отключиться',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('Выйти с несохранёнными черновиками?');
  await page.getByRole('button',{name:'Продолжить проверку',exact:true}).click();
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.locator('.draft-status')).toContainText('Unsaved draft');
  await page.getByRole('button',{name:'Save decision',exact:true}).click();
  await expect(page.locator('.save-message')).toContainText('Saved in demo memory');
  await expect(page.locator('.event-card').first()).toContainText('Further review needed');
  await expect(page.locator('.draft-status')).toContainText('Saved:');
  expect(await page.evaluate(() => window.dispatchEvent(new Event('beforeunload',{cancelable:true})))).toBe(true);
  await page.getByRole('button',{name:'Русский',exact:true}).click();
  await page.screenshot({path:'apps/web/dist/qa-polish-review.png',fullPage:true});
  await page.getByLabel('Заметка',{exact:true}).fill('Another temporary draft');
  await page.getByRole('button',{name:'Отключиться',exact:true}).click();
  await page.getByRole('button',{name:'Выйти без сохранения',exact:true}).click();
  await page.getByRole('button',{name:'Открыть синтетическое демо'}).click();
  await page.getByRole('button',{name:'Открыть дело synthetic-positive'}).click();
  await page.getByText('Заметка проверяющего · добавить',{exact:true}).click();
  await expect(page.getByLabel('Заметка',{exact:true})).toHaveValue('');
});

test('incorrect review acknowledgement preserves draft; old polling cannot revert a valid save', async ({ page }) => {
  const data = JSON.parse(readFileSync('packages/contracts/fixtures/ui-positive.json','utf8'));
  data.is_synthetic = false; data.rules[0].enabled = true;
  let mismatch = true; let polls = 0;
  await page.route('**/health/ready', route => route.fulfill({json:{ready:true,mode:'server',contract_version:'1.0.0'}}));
  await page.route('**/api/ui/**', async route => {
    if (route.request().url().endsWith('/cases')) { await route.fulfill({json:{items:[]}}); return; }
    if (route.request().method() === 'PUT') {
      await route.fulfill({json:{...route.request().postDataJSON(),event_id:mismatch?'wrong-event':data.events[0].event_id,updated_at:'2026-10-18T12:00:00Z'}}); mismatch = false; return;
    }
    polls++; await route.fulfill({json:data});
  });
  await page.goto('/#case=synthetic-positive');
  await page.getByLabel('Ключ доступа',{exact:true}).fill('synthetic-key');
  await page.getByRole('button',{name:'Открыть рабочее пространство'}).click();
  await page.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await page.getByRole('button',{name:'Сохранить решение'}).click();
  await expect(page.getByRole('alert')).toContainText('для другого события');
  await expect(page.locator('.draft-status')).toContainText('Черновик не сохранён');
  await page.getByRole('button',{name:'Сохранить решение'}).click();
  await expect(page.locator('.event-card').first()).toContainText('Подтверждено проверяющим');
  const before = polls;
  await expect.poll(() => polls).toBeGreaterThan(before);
  await expect(page.getByRole('button',{name:'Подтвердить',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('.event-card').first()).toContainText('Подтверждено проверяющим');
  await expect(page.getByRole('heading',{name:'Обнаружены признаки возможных нарушений',exact:true})).toBeVisible();
});

test('save action stays inside the scrollable evidence panel with a long unsaved note', async ({ page }) => {
  await page.goto('/?demo=1#case=synthetic-positive');
  await page.getByText('Заметка проверяющего · добавить',{exact:true}).click();
  await page.getByLabel('Заметка',{exact:true}).fill('Synthetic note. '.repeat(100));
  await page.locator('.desk').scrollIntoViewIfNeeded();
  await page.locator('.detail-body').evaluate(element => { element.scrollTop = 0; });
  const bounds = await page.locator('.detail-panel').boundingBox();
  const button = page.getByRole('button',{name:'Сохранить решение',exact:true});
  const action = await button.boundingBox();
  expect(action!.y + action!.height).toBeLessThanOrEqual(bounds!.y + bounds!.height);
  expect(action!.y).toBeGreaterThanOrEqual(bounds!.y);
  expect(await button.evaluate(element => { const r = element.getBoundingClientRect(); return element.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)); })).toBe(true);
  await page.screenshot({path:'apps/web/dist/qa-polish-sticky-save.png',fullPage:true});
  await button.click();
  await expect(page.locator('.save-message')).toContainText('Сохранено в памяти демо');
});

test('local upload preview sends no file, releases Blob URLs and permits unsupported browser codecs', async ({ page }) => {
  let uploads = 0;
  await page.addInitScript(() => { const revoke = URL.revokeObjectURL; (window as any).previewRevoked = 0; URL.revokeObjectURL = value => { (window as any).previewRevoked++; revoke(value); }; });
  await page.route('**/api/ui/cases', route => route.fulfill({json:{items:[]}}));
  await page.route('**/health/ready', route => route.fulfill({json:{ready:true,mode:'server',contract_version:'1.0.0'}}));
  await page.route('**/api/v1/analyze', route => { uploads++; return route.fulfill({status:503,json:{error:{code:'UNAVAILABLE',message:'Synthetic test'}}}); });
  await page.goto('/');
  await page.getByLabel('Ключ доступа',{exact:true}).fill('synthetic-key');
  await page.getByRole('button',{name:'Открыть рабочее пространство'}).click();
  await page.getByRole('button',{name:'Новый анализ',exact:true}).click();
  const input = page.locator('input[type=file]');
  await input.setInputFiles({name:'generated-color.mov',mimeType:'video/quicktime',buffer:Buffer.from(readFileSync('apps/web/tests/assets/synthetic-preview.base64.txt','utf8'),'base64')});
  await expect.poll(() => page.locator('.local-preview video').evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThan(0);
  await expect(page.locator('.local-preview .mono')).toContainText('×');
  expect(uploads).toBe(0);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'apps/web/dist/qa-polish-upload-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Убрать выбранный файл'}).click();
  await expect(page.locator('.local-preview')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => (window as any).previewRevoked)).toBeGreaterThan(0);
  await input.setInputFiles({name:'browser-unsupported.mov',mimeType:'video/quicktime',buffer:Buffer.from('synthetic invalid container')});
  await expect(page.locator('.local-preview')).toContainText('Файл можно отправить');
  await expect(page.getByRole('button',{name:'Начать анализ',exact:true})).toBeEnabled();
  expect(uploads).toBe(0);
  await page.getByRole('button',{name:'Начать анализ',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('не готовы');
  expect(uploads).toBe(1);
  await page.getByRole('button',{name:'Закрыть',exact:true}).click();
  await expect.poll(() => page.evaluate(() => (window as any).previewRevoked)).toBeGreaterThan(1);
});
