'use strict';
const $ = id => document.getElementById(id);
let scenarios = [], result = null, running = false, liveReady = false;
function refreshButtons() { $('recorded').disabled = running; $('live').disabled = running || !liveReady; $('scenario').disabled = running; }
async function readiness() {
  const response = await fetch('/health/ready');
  if (!response.ok) throw new Error('Не удалось проверить готовность сервера');
  const body = await response.json(); liveReady = body.gemini_live_ready;
  $('health').textContent = liveReady ? 'Сервер доступен · Gemini Free Tier разрешён для короткой проверки' : `Сервер доступен · записанный режим работает · новый Gemini заблокирован: ${body.gemini_block_reason}`;
  refreshButtons();
}
async function request(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type':'application/json', 'X-API-Key':$('key').value, ...options.headers}});
  const body = await response.json();
  if (!response.ok) throw new Error(`${response.status}: ${typeof body.detail === 'string' ? body.detail : 'Запрос отклонён'}`);
  return body;
}
function selectVideo() { const row = scenarios.find(x => x.id === $('scenario').value); if (row) $('video').src = row.video_url; }
async function run(engine) {
  if (!$('key').value) { $('status').textContent = 'Введите ключ лаборатории.'; $('key').focus(); return; }
  running = true; result = null; $('download').disabled = true; refreshButtons(); $('result').textContent = ''; $('summary').textContent = 'Выполняется проверка…';
  $('status').textContent = engine === 'gemini' ? 'Новый запрос к Gemini: ожидаем ответ…' : 'Сервер декодирует синтетику и проверяет геометрию…';
  try {
    const job = await request('/api/synthetic/jobs', {method:'POST', body:JSON.stringify({scenario:$('scenario').value, engine})});
    const deadline = Date.now() + 180000;
    while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      const state = await request(`/api/synthetic/jobs/${encodeURIComponent(job.job_id)}`);
      if (state.status === 'failed') throw new Error(state.error.code);
      if (state.status !== 'done') continue;
      result = state; const r = state.result;
      $('summary').textContent = `Пересечения слева направо: ${r.geometry_result.event_times_sec.map(x=>x+' с').join(', ') || 'нет'}. Исходный Gemini: ${r.raw_gemini_result.event_times_sec.map(x=>x+' с').join(', ') || 'нет'}. Новых запросов: ${r.new_gemini_requests}.`;
      $('result').textContent = JSON.stringify(state, null, 2);
      $('status').textContent = `Проверка завершена на облачном сервере за ${state.elapsed_sec} с.`;
      $('download').disabled = false; return;
    }
    throw new Error('Истекло ожидание. Результат не считается отрицательным.');
  } catch (error) { $('status').textContent = `Проверка не завершена: ${error.message}`; $('summary').textContent = 'Нет достоверного результата.'; }
  finally { running = false; await readiness().catch(()=>{liveReady=false;refreshButtons();}); }
}
$('recorded').addEventListener('click', () => run('recorded'));
$('live').addEventListener('click', () => run('gemini'));
$('scenario').addEventListener('change', selectVideo);
$('download').addEventListener('click', () => {
  if (!result) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(result,null,2)], {type:'application/json'}));
  const link = document.createElement('a'); link.href=url; link.download=`synthetic-${result.scenario}-${result.job_id}.json`; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
});
(async()=>{try {const response=await fetch('/api/synthetic/scenarios'); if(!response.ok)throw new Error('Сценарии недоступны');const body=await response.json();scenarios=body.scenarios;for(const row of scenarios){const option=document.createElement('option');option.value=row.id;option.textContent=row.title;$('scenario').append(option);}selectVideo();await readiness();}catch(error){$('health').textContent=error.message;}})();
