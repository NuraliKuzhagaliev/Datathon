// New real local analysis in the packaged EXE. Private contents stay on disk.
const fs = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { randomUUID } = require('node:crypto');
const { _electron: electron, expect } = require('@playwright/test');
const root = path.resolve(__dirname, '..');
const { values } = parseArgs({ options: { executable: { type: 'string' }, output: { type: 'string' } } });
const executable = path.resolve(values.executable || path.join(root,'apps/desktop/dist/offline/win-unpacked/CashProof.exe'));
const packagedVersion = fs.readFileSync(path.join(path.dirname(executable), 'resources/backend/app/cashproof/__init__.py'), 'utf8').match(/^__version__ = "([0-9.]+)"$/m)?.[1];
if (!packagedVersion) throw new Error('Cannot determine packaged backend version.');
const privateRoot = path.join(root, 'private-data');
const output = path.resolve(values.output || path.join(privateRoot, 'packaged-verification', randomUUID()));
const relativeOutput = path.relative(privateRoot, output);
if (!relativeOutput || relativeOutput.startsWith('..') || path.isAbsolute(relativeOutput)) throw new Error('Verification output must be a new private-data subdirectory.');
fs.mkdirSync(path.dirname(output), {recursive:true});
fs.mkdirSync(output); // Preserve every earlier receipt and case on repeat runs.

(async () => {
  const {video} = JSON.parse(fs.readFileSync(path.join(root,'private-data/live-browser-integration/input.json'),'utf8'));
  const started = Date.now();
  const app = await electron.launch({executablePath:executable,args:[],timeout:60000});
  let origin, summary;
  let external = 0, errors = 0;
  const externalOrigins = new Set();
  try {
    await app.evaluate(({app}, directory) => app.setPath('userData',directory), output);
    const packaged = await app.evaluate(({app}) => app.isPackaged);
    if (!packaged) throw new Error('Expected packaged application');
    const context = app.context();
    await context.route('**/*', route => {
      const url = route.request().url();
      if (/^(file:|blob:|data:)/.test(url) || /^http:\/\/127\.0\.0\.1:\d+\//.test(url)) return route.continue();
      external++; externalOrigins.add(new URL(url).origin); return route.abort();
    });
    context.on('page', page => page.on('pageerror',()=>errors++));
    const launcher = await app.firstWindow();
    const opened = app.waitForEvent('window',{timeout:270000});
    await launcher.locator('#local').click();
    const viewer = await opened;
    await expect(viewer.getByRole('heading',{name:'Проверка операций',exact:true})).toBeVisible({timeout:30000});
    origin = new URL(viewer.url()).origin;
    const health = await (await context.request.get(origin+'/health/ready')).json();
    if (!health.ready || health.mode!=='offline' || health.contract_version!=='1.0.0') throw new Error('Unexpected model readiness');
    const startupSec = (Date.now()-started)/1000;
    await viewer.getByRole('button',{name:'English',exact:true}).click();
    await viewer.getByRole('button',{name:'New analysis',exact:true}).click();
    await viewer.locator('input[type=file]').setInputFiles(video);
    const analysisStarted=Date.now();
    const accepted=viewer.waitForResponse(r=>r.url().endsWith('/api/v1/analyze') && r.request().method()==='POST');
    await viewer.getByRole('button',{name:'Start analysis',exact:true}).click();
    if ((await accepted).status()!==202) throw new Error('Real upload rejected');
    await expect(viewer.getByRole('heading',{name:/^(No violation detected|Signs of possible violations detected)$/}).first()).toBeVisible({timeout:280000});
    const analysisSec=(Date.now()-analysisStarted)/1000;
    const state=await viewer.evaluate(async()=>{
      const config=await window.cashproof.getConfig();
      const id=new URLSearchParams(location.hash.slice(1)).get('case');
      const detail=await (await fetch('/api/ui/cases/'+id,{headers:{'X-API-Key':config.apiKey}})).json();
      return {status:detail.status,is_synthetic:detail.is_synthetic,event_count:detail.events.length,backend_version:detail.model_version.split(';backend=')[1]};
    });
    if (state.status!=='done' || state.is_synthetic!==false || state.backend_version!==packagedVersion) throw new Error('Unexpected real runtime result');
    summary={packaged:true,new_real_analysis_completed:true,backend_version:state.backend_version,health,startup_sec:startupSec,analysis_sec:analysisSec,input_bytes:fs.statSync(video).size,review_real_events_verified:false,host_network_disconnected:false,os_offline_qualified:false};
    fs.writeFileSync(path.join(output,'technical-checkpoint.json'),JSON.stringify(summary,null,2));
    await app.evaluate(({session}, destination)=>{
      globalThis.cashproofDownloadStatus='pending';
      session.defaultSession.once('will-download', (_event,item)=>{
        item.setSavePath(destination);
        item.once('done',(_event,state)=>{globalThis.cashproofDownloadStatus=state;});
      });
    },path.join(output,'case.zip'));
    await viewer.getByRole('button',{name:'Export case',exact:true}).click();
    await expect.poll(()=>app.evaluate(()=>globalThis.cashproofDownloadStatus),{timeout:30000}).toBe('completed');
    await viewer.reload();
    await expect(viewer.getByRole('heading',{name:/^(No violation detected|Signs of possible violations detected)$/}).first()).toBeVisible();
    if (errors) throw new Error('Renderer JavaScript errors');
    Object.assign(summary,{export_downloaded:true,reload_restored:true,browser_errors:errors,external_requests_blocked:external,external_origins:[...externalOrigins]});
  } finally { await app.close(); }
  let stopped=false;
  for(let i=0;i<20;i++){
    try { await fetch(origin+'/health/live',{signal:AbortSignal.timeout(500)}); }
    catch {stopped=true;break;}
    await new Promise(resolve=>setTimeout(resolve,500));
  }
  if (!stopped) throw new Error('Backend still reachable after application close');
  summary.backend_stopped_after_app_close=true;
  fs.writeFileSync(path.join(output,'technical-summary.json'),JSON.stringify(summary,null,2));
  console.log(JSON.stringify(summary));
})().catch(error=>{
  fs.writeFileSync(path.join(output,'private-error.log'),String(error.stack));
  console.log(JSON.stringify({completed:false,error_type:error.name,diagnostics_saved_privately:true}));
  process.exitCode=1;
});
