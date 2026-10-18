import { useEffect, useRef, useState } from 'react';
import { Cloud, Download, RefreshCw } from 'lucide-react';
import { useI18n } from '../i18n';

type Health = { synthetic_only: true; recorded_replay_ready: boolean; gemini_live_ready: boolean; gemini_block_reason: string | null; model: string; live_requests_started_this_instance: number; max_live_requests_this_instance: number; results_ephemeral: boolean };
type Result = { job_id: string; status: 'done'; scenario: string; engine: 'recorded' | 'gemini'; elapsed_sec: number; result: { synthetic_only: true; new_gemini_requests: number; model_version: string; raw_gemini_result: { event_times_sec: number[] }; geometry_result: { event_times_sec: number[] }; source_sha256: string; prompt_version?: string; model_input_transform?: {method: string} } };
type Props = { scenario: string; title: string; videoUrl: string; duration: number; sourceHash: string };

function validTimes(value: unknown, duration: number): value is number[] {
  return Array.isArray(value) && value.length <= 24 && value.every((t, i) => typeof t === 'number' && Number.isFinite(t) && t >= 0 && t < duration && (i === 0 || t > value[i - 1]));
}

export function CloudSynthetic({ scenario, title, videoUrl, duration, sourceHash }: Props) {
  const { locale } = useI18n(); const text = (ru: string, en: string) => locale === 'en' ? en : ru;
  const [key, setKey] = useState(''), [health, setHealth] = useState<Health>(), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [status, setStatus] = useState(''), [result, setResult] = useState<Result>();
  const controller = useRef<AbortController | null>(null), video = useRef<HTMLVideoElement>(null);
  useEffect(() => { setResult(undefined); setError(''); setStatus(''); setBusy(false); return () => { controller.current?.abort(); controller.current = null; }; }, [scenario]);

  async function request(path: string, signal: AbortSignal, body?: object) {
    const response = await fetch(`/api/synthetic/${path}`, { method: body ? 'POST' : 'GET', credentials: 'omit', signal,
      headers: { 'X-API-Key': key.trim(), ...(body ? { 'Content-Type': 'application/json' } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    if (response.status === 401) throw new Error(text('Ключ лаборатории не принят.', 'The laboratory key was rejected.'));
    if (response.status === 429) throw new Error(text('Сервер занят. Запустите проверку позже.', 'The server is busy. Start the check later.'));
    if (response.status === 410) throw new Error(text('Задание утрачено после перезапуска Render. Результат не получен.', 'The job was lost after a Render restart. No result is available.'));
    const content = await response.json().catch(() => null) as Record<string, unknown> | null;
    if (!response.ok || !content) throw new Error(response.status === 503 ? text('Новые запросы Gemini заблокированы: проверьте Free Tier и квоту.', 'New Gemini requests are blocked: check Free Tier verification and quota.') : text('Render недоступен или вернул некорректный ответ.', 'Render is unavailable or returned an invalid response.'));
    return content;
  }
  function readHealth(value: Record<string, unknown>): Health {
    if (value.synthetic_only !== true || typeof value.model !== 'string' || typeof value.gemini_live_ready !== 'boolean' || typeof value.recorded_replay_ready !== 'boolean') throw new Error(text('Неподтверждённый синтетический сервис.', 'Unverified synthetic service.'));
    return value as Health;
  }
  async function connect() {
    if (!key.trim() || busy) return;
    const current = new AbortController(); controller.current?.abort(); controller.current = current;
    setBusy(true); setError(''); setStatus(text('Подключаем Render. После простоя запуск может занять около минуты…', 'Connecting to Render. After idle, startup can take about a minute…'));
    const timeout = setTimeout(() => current.abort(), 90000);
    try { setHealth(readHealth(await request('session', current.signal))); setStatus(''); }
    catch (e) { setError(e instanceof Error && e.name !== 'AbortError' ? e.message : text('Соединение не установлено. Повторите подключение.', 'Connection was not established. Retry connecting.')); }
    finally { clearTimeout(timeout); if (controller.current === current) setBusy(false); }
  }
  async function run(engine: 'recorded' | 'gemini') {
    if (!health || busy) return;
    const current = new AbortController(); controller.current?.abort(); controller.current = current;
    setBusy(true); setError(''); setResult(undefined); setStatus(engine === 'gemini' ? text('Gemini просматривает синтетические кадры в облаке…', 'Gemini is examining synthetic frames in the cloud…') : text('Render обрабатывает сохранённый ответ и исходные кадры…', 'Render is processing the recorded response and source frames…'));
    const timeout = setTimeout(() => current.abort(), 180000);
    try {
      const submitted = await request('jobs', current.signal, { scenario, engine });
      if (typeof submitted.job_id !== 'string' || !/^[a-f0-9-]+$/.test(submitted.job_id)) throw new Error(text('Некорректный ID задания.', 'Invalid job ID.'));
      while (!current.signal.aborted) {
        await new Promise<void>((resolve, reject) => { const stop = () => { clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')); }; const timer = setTimeout(() => { current.signal.removeEventListener('abort', stop); resolve(); }, 1000); current.signal.addEventListener('abort', stop, { once: true }); });
        const row = await request(`jobs/${submitted.job_id}`, current.signal);
        if (row.status === 'processing') continue;
        if (row.status === 'failed') throw new Error(text('Анализ не завершён. Автоматического повтора и отрицательного вердикта нет.', 'Analysis failed. There is no automatic retry or negative verdict.'));
        const parsed = row as unknown as Result;
        if (parsed.status !== 'done' || parsed.scenario !== scenario || parsed.job_id !== submitted.job_id || parsed.engine !== engine || parsed.result?.synthetic_only !== true || parsed.result.source_sha256 !== sourceHash || !(engine === 'recorded' ? parsed.result.new_gemini_requests === 0 : parsed.result.new_gemini_requests === 1 || (parsed.result.new_gemini_requests === 2 && parsed.result.prompt_version === 'native-reference-v12-review')) || !validTimes(parsed.result.raw_gemini_result?.event_times_sec, duration) || !validTimes(parsed.result.geometry_result?.event_times_sec, duration)) throw new Error(text('Некорректный результат анализа.', 'Invalid analysis result.'));
        setResult(parsed); setStatus(text('Облачная проверка завершена.', 'Cloud check completed.'));
        const updated = await request('session', current.signal); setHealth(readHealth(updated));
        return;
      }
    } catch (e) { if (!current.signal.aborted) setError(e instanceof Error ? e.message : text('Анализ не завершён.', 'Analysis did not finish.')); else if (controller.current === current) setStatus(text('Ожидание остановлено. Сервер может завершить уже принятое задание.', 'Waiting stopped. The server may finish an accepted job.')); }
    finally { clearTimeout(timeout); if (controller.current === current) setBusy(false); }
  }
  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `cashproof-cloud-${result.scenario}-${result.job_id}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function times(values: number[]) { return values.length ? values.map((value, i) => <button className="lab-time" key={i} onClick={() => { if (video.current) video.current.currentTime = value; }}>{value.toFixed(1)} {text('с', 's')}</button>) : <span>{text('Пересечений слева направо не обнаружено', 'No left-to-right crossing detected')}</span>; }
  return <article className="lab-case cloud-lab">
    <div className="lab-case-heading"><div><span className="eyebrow"><Cloud size={14}/> RENDER · GEMINI</span><h2>{title}</h2></div><span className="tag">{text('Только синтетика', 'Synthetic only')}</span></div>
    <video ref={video} src={videoUrl} controls preload="metadata" aria-label={title}/>
    <p className="lab-explanation">{text('Анализ выполняется на Render и у Gemini. Ваш компьютер не служит сервером. Ключ Gemini скрыт на сервере; ниже нужен отдельный ключ лаборатории.', 'Analysis runs on Render and Gemini. Your computer is not a server. The Gemini key stays on the server; enter the separate laboratory key below.')}</p>
    {!health ? <form onSubmit={e => { e.preventDefault(); void connect(); }}><label className="field">{text('Ключ облачной лаборатории', 'Cloud laboratory key')}<input type="password" autoComplete="off" spellCheck={false} value={key} disabled={busy} onChange={e => setKey(e.target.value)} required/></label><button className="button primary" disabled={busy || !key.trim()}><Cloud size={16}/>{text('Подключить Render', 'Connect Render')}</button></form> : <>
      <div className="cloud-connection"><strong>{text('Render подключён', 'Render connected')}</strong><span>{health.model}</span><button className="text-button" disabled={busy} onClick={() => { setHealth(undefined); setKey(''); setResult(undefined); }}>{text('Отключиться', 'Disconnect')}</button></div>
      {!health.gemini_live_ready && <p className="notice">{text('Новые запросы Gemini заблокированы проверкой Free Tier или квотой. Сохранённые ответы доступны.', 'New Gemini requests are blocked by Free Tier verification or quota. Recorded responses remain available.')}</p>}
      <div className="lab-actions"><button className="button primary" disabled={busy || !health.gemini_live_ready} onClick={() => void run('gemini')}><Cloud size={16}/>{text('Новый анализ Gemini', 'New Gemini analysis')}</button><button className="button secondary" disabled={busy} onClick={() => void run('recorded')}><RefreshCw size={16}/>{text('Запись + расчёт на Render', 'Recording + Render computation')}</button>{busy && <button className="text-button" onClick={() => controller.current?.abort()}>{text('Остановить ожидание', 'Stop waiting')}</button>}</div>
    </>}
    <p role="status" className="lab-progress">{status}</p>{error && <p role="alert" className="notice">{error}</p>}
    {result && <div className="cloud-result"><h3>{result.engine === 'gemini' ? text('Новый ответ самой Gemini', 'New Gemini model response') : text('Сохранённый ответ Gemini', 'Recorded Gemini response')}</h3><div data-testid="cloud-model-times">{times(result.result.raw_gemini_result.event_times_sec)}</div><p className="muted">{result.result.model_version} · {text('Новых запросов', 'New requests')}: {result.result.new_gemini_requests} · {result.elapsed_sec} {text('с', 's')}</p>{result.result.model_input_transform?.method === 'static_red_reference_overlay' && <p className="lab-explanation">{text('В синтетическом входе усилена видимость неподвижной красной линии. Модель сама указала пересечения и исходные времена; геометрия их не исправляет.', 'The synthetic input reinforces the fixed red reference line. The model selected crossings and source times; geometry does not correct them.')}</p>}<details><summary>{text('Отдельная диагностика геометрии', 'Separate geometry diagnostic')}</summary><p>{text('Независимый алгоритм для фигур. Его результат не считается точностью Gemini.', 'An independent algorithm for shapes. Its result is not Gemini accuracy.')}</p>{times(result.result.geometry_result.event_times_sec)}</details><button className="button secondary" onClick={download}><Download size={16}/>{text('Скачать облачный JSON', 'Download cloud JSON')}</button></div>}
    <p className="lab-explanation">{text('Ключ хранится только в памяти окна. Render Free может засыпать; результаты исчезают при перезапуске. Загружать банковские или другие пользовательские видео здесь нельзя.', 'The key stays only in window memory. Render Free may sleep; results disappear on restart. Banking footage and other user videos cannot be uploaded here.')}</p>
  </article>;
}
