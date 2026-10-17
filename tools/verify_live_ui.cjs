// Local-only real UI probe. No screenshots, traces, captions or keys in output.
const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('@playwright/test');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'private-data/live-browser-integration');

(async () => {
  const key = JSON.parse(fs.readFileSync(path.join(root, 'runtime-data/team-server/credentials.json'), 'utf8')).operator;
  const { video } = JSON.parse(fs.readFileSync(path.join(output, 'input.json'), 'utf8'));
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const context = await browser.newContext({acceptDownloads:true});
  let external = 0, errors = 0;
  const externalOrigins = new Set(), errorTypes = new Set();
  await context.route('**/*', route => {
    const url = route.request().url();
    if (!url.startsWith('http://127.0.0.1:8000/') && !url.startsWith('blob:') && !url.startsWith('data:')) { external++; externalOrigins.add(new URL(url).origin); return route.abort(); }
    return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => { errors++; errorTypes.add(error.name); });
  const started = Date.now();
  try {
    await page.goto('http://127.0.0.1:8000/');
    await page.getByRole('button',{name:'English',exact:true}).click();
    await page.getByLabel('Access key',{exact:true}).fill(key);
    await page.getByRole('button',{name:'Open workspace',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Operation review',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'New analysis',exact:true}).click();
    await page.locator('input[type=file]').setInputFiles(video);
    const uploadStarted = Date.now();
    const accepted = page.waitForResponse(r => r.url().endsWith('/api/v1/analyze') && r.request().method()==='POST');
    await page.getByRole('button',{name:'Start analysis',exact:true}).click();
    const response = await accepted;
    if (response.status()!==202) throw new Error('Upload was not accepted');
    const uploadSec = (Date.now()-uploadStarted)/1000;
    const job = (await response.json()).job_id;
    const headers = {'X-API-Key':key};
    let detail;
    while (Date.now()-uploadStarted < 300000) {
      detail = await (await context.request.get(`http://127.0.0.1:8000/api/ui/cases/${job}`,{headers})).json();
      if (detail.status !== 'processing') break;
      await new Promise(resolve=>setTimeout(resolve,500));
    }
    if (detail.status!=='done' || detail.is_synthetic!==false) throw new Error('Real analysis did not finish');
    const heading = detail.model_result.verdict==='violation' ? 'Signs of possible violations detected' : 'No violation detected';
    await expect(page.getByRole('heading',{name:heading,exact:true}).first()).toBeVisible({timeout:15000});
    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('button',{name:'Export case',exact:true}).click();
    await (await downloadEvent).saveAs(path.join(output,'case.zip'));
    if ((await page.evaluate(()=>JSON.stringify(localStorage))).includes(key)) throw new Error('Credential persisted');
    await page.reload();
    await page.getByLabel('Access key',{exact:true}).fill(key);
    await page.getByRole('button',{name:'Open workspace',exact:true}).click();
    await expect(page.getByRole('heading',{name:heading,exact:true}).first()).toBeVisible();
    if (errors || external) {
      console.log(JSON.stringify({browser_errors:errors,external_requests:external,external_origins:[...externalOrigins],error_types:[...errorTypes]}));
      throw new Error('Browser errors or external requests');
    }
    const result={completed:true,admission_http:202,upload_sec:uploadSec,total_browser_sec:(Date.now()-started)/1000,export_downloaded:true,relogin_restored:true,is_synthetic:false,browser_errors:errors,external_requests:external,review_real_events_verified:false};
    fs.writeFileSync(path.join(output,'technical-summary.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error=>{
  fs.mkdirSync(output,{recursive:true});
  fs.writeFileSync(path.join(output,'private-error.log'),String(error.stack));
  console.log(JSON.stringify({completed:false,error_type:error.name,diagnostics_saved_privately:true}));
  process.exitCode=1;
});
