import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Download, FlaskConical, Play, ScanLine, ShieldCheck, XCircle } from 'lucide-react';
import { useI18n } from '../i18n';
import { ambiguousIndices, crossingsFromSides, refineInBrowser, type Side, type SourceFrame } from './syntheticGeometry';
import '../styles/synthetic-lab.css';
import { CloudSynthetic } from './CloudSynthetic';

type Recording = {
  id: string; title_ru: string; title_en: string; video_url: string; video_sha256: string;
  duration_sec: number; frames: SourceFrame[]; recorded_at_utc: string; gemini_sides: Side[];
  gemini_event_times_sec: number[]; reference_event_times_sec: number[]; recorded_hybrid_event_times_sec: number[];
};
type Recordings = { version: number; synthetic_only: boolean; model: string; fresh_api_completed: number; fresh_api_planned: number; cases: Recording[] };
const IDS = new Set(['near_line_start', 'forward', 'reverse', 'repeated', 'early', 'late', 'near_miss', 'stationary_overlap']);

async function loadRecordings(signal: AbortSignal): Promise<Recordings> {
  const response = await fetch('/synthetic-demo/recordings.json', { signal, credentials: 'omit' });
  if (!response.ok) throw new Error('Recordings unavailable');
  const value = await response.json() as Recordings;
  if (value.version !== 1 || value.synthetic_only !== true || !Array.isArray(value.cases) || value.cases.length !== 8) throw new Error('Invalid demo data');
  const seen = new Set<string>();
  for (const item of value.cases) {
    if (!IDS.has(item.id) || seen.has(item.id) || item.video_url !== `/synthetic-demo/${item.id}.mp4` || !/^[a-f0-9]{64}$/.test(item.video_sha256)) throw new Error('Invalid demo source');
    if (!Array.isArray(item.frames) || !Array.isArray(item.gemini_sides) || item.frames.length !== item.gemini_sides.length || !item.frames.length || item.frames.length > 48) throw new Error('Invalid demo observations');
    if (item.gemini_sides.some(s => !['left', 'on', 'right'].includes(s)) || item.frames.some((f, i) => !Number.isFinite(f.timestamp_sec) || f.timestamp_sec < 0 || f.timestamp_sec >= item.duration_sec || (i > 0 && f.timestamp_sec <= item.frames[i - 1].timestamp_sec))) throw new Error('Invalid source timeline');
    seen.add(item.id);
  }
  return value;
}

function RecordedCase({ item }: { item: Recording }) {
  const { locale } = useI18n();
  const text = (ru: string, en: string) => locale === 'en' ? en : ru;
  const video = useRef<HTMLVideoElement>(null), controller = useRef<AbortController | null>(null);
  const [ready, setReady] = useState(false), [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [result, setResult] = useState<{ sides: Side[]; times: number[]; elapsed: number }>();
  const [error, setError] = useState('');
  useEffect(() => () => controller.current?.abort(), []);
  const matches = result && result.times.length === item.reference_event_times_sec.length && result.times.every((t, i) => Math.abs(t - item.reference_event_times_sec[i]) <= 0.5);

  async function verify() {
    if (!video.current || !ready || busy) return;
    const current = new AbortController(); controller.current = current;
    setBusy(true); setError(''); setResult(undefined);
    const start = performance.now();
    try {
      const sides = await refineInBrowser(video.current, item.frames, item.gemini_sides, current.signal, (done, total) => setProgress({ done, total }));
      const times = crossingsFromSides(sides, item.frames).filter(c => c.direction === 'left_to_right').map(c => c.time_sec);
      if (!current.signal.aborted) { setResult({ sides, times, elapsed: (performance.now() - start) / 1000 }); video.current.currentTime = times[0] ?? 0; }
    } catch {
      if (!current.signal.aborted) setError(text('Не удалось прочитать кадры или однозначно измерить фигуры. Повторите проверку.', 'Could not decode frames or measure the shapes unambiguously. Retry the check.'));
    } finally { if (!current.signal.aborted) setBusy(false); }
  }
  function download() {
    if (!result) return;
    const report = { synthetic_only: true, mode: 'recorded_gemini_plus_live_browser_geometry', fresh_cloud_requests: 0, model: 'gemini-2.5-flash', source_sha256: item.video_sha256, scenario: item.id, recorded_at_utc: item.recorded_at_utc, raw_gemini_event_times_sec: item.gemini_event_times_sec, browser_event_times_sec: result.times, reference_event_times_sec: item.reference_event_times_sec, source_frames: item.frames, gemini_sides: item.gemini_sides, browser_sides: result.sides, passed_within_0_5_sec: matches, browser_elapsed_sec: result.elapsed };
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `cashproof-synthetic-${item.id}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function times(values: number[]) {
    return values.length ? values.map((time, i) => <button className="lab-time" key={i} disabled={!ready || busy} onClick={() => { if (video.current) video.current.currentTime = time; }}>{time.toFixed(1)} {text('с', 's')}</button>) : <span className="muted">{text('Пересечений слева направо нет', 'No left-to-right crossing')}</span>;
  }
  return <article className="lab-case">
    <div className="lab-case-heading"><div><span className="eyebrow">{text('ВЫБРАННЫЙ СЦЕНАРИЙ', 'SELECTED SCENARIO')}</span><h2>{locale === 'en' ? item.title_en : item.title_ru}</h2></div><span className="tag">{item.duration_sec} {text('секунд', 'seconds')}</span></div>
    <div className="lab-video"><video ref={video} src={item.video_url} controls={!busy} playsInline preload="auto" onLoadedData={() => setReady(true)} onError={() => { setReady(false); setError(text('Синтетическое видео недоступно.', 'Synthetic video unavailable.')); }} aria-label={text('Синтетическое видео с синим объектом и красной линией', 'Synthetic video with a blue object and red line')}/></div>
    <p className="lab-explanation">{text('Событие — центр синего квадрата пересекает красную линию слева направо. Обратное движение и касание краем не считаются событием.', 'An event occurs when the blue square’s center crosses the red line from left to right. Reverse movement and edge contact do not count.')}</p>
    <div className="lab-actions"><button className="button primary" onClick={() => void verify()} disabled={!ready || busy}><ScanLine size={18}/>{busy ? text('Чтение кадров…', 'Reading frames…') : text('Проверить геометрию в браузере', 'Check geometry in browser')}</button>{busy && <button className="button secondary" onClick={() => { controller.current?.abort(); setBusy(false); }}>{text('Остановить', 'Stop')}</button>}{result && <button className="button secondary" onClick={download}><Download size={16}/>{text('Скачать отчёт', 'Download report')}</button>}</div>
    <div aria-live="polite" className="lab-progress">{busy ? <><progress value={progress.done} max={Math.max(1, progress.total)}/><span>{text('Измерено кадров', 'Frames measured')}: {progress.done}/{progress.total}</span></> : result ? <span className={matches ? 'lab-success' : 'lab-failure'}>{matches ? <CheckCircle2 size={17}/> : <XCircle size={17}/>} {matches ? text('Проверка пройдена', 'Check passed') : text('Результат отличается от эталона', 'Result differs from reference')} · {result.elapsed.toFixed(2)} {text('с на этом устройстве', 's on this device')}</span> : <span>{text('Проверка выполняется на этом устройстве. Запросов к облачному ИИ: 0.', 'Verification runs on this device. Cloud AI requests: 0.')}</span>}</div>
    {error && <div className="notice" role="alert">{error}</div>}
    <div className="lab-results"><section><h3>{text('Записанный ответ Gemini', 'Recorded Gemini result')}</h3>{times(item.gemini_event_times_sec)}<small>{text('Исходный вывод модели сохранён без изменений.', 'The original model output is preserved unchanged.')}</small></section><section className="lab-local-result"><h3>{text('После проверки пикселей', 'After pixel verification')}</h3>{result ? times(result.times) : <span className="muted">{text('Нажмите кнопку проверки', 'Run the verification above')}</span>}<small>{text('Время берётся из исходных кадров.', 'Times come from original source frames.')}</small></section><section><h3>{text('Эталон синтетического теста', 'Synthetic reference')}</h3>{times(item.reference_event_times_sec)}<small>{text('Используется для оценки, а не для поиска события.', 'Used for scoring, not for detection.')}</small></section></div>
    <details className="lab-provenance"><summary>{text('Происхождение результата', 'Result provenance')}</summary><p>{text('Gemini 2.5 Flash · записанный API-ответ от ', 'Gemini 2.5 Flash · recorded API response from ')}{new Date(item.recorded_at_utc).toLocaleString(locale === 'en' ? 'en-GB' : 'ru-RU')}</p><p>{text('Кадров в записи', 'Recorded frames')}: {item.frames.length} · {text('Кадров для измерения', 'Frames to measure')}: {ambiguousIndices(item.gemini_sides).length}</p><p className="hash">SHA-256: {item.video_sha256}</p></details>
  </article>;
}

export function SyntheticLab() {
  const { locale } = useI18n(); const text = (ru: string, en: string) => locale === 'en' ? en : ru;
  const [data, setData] = useState<Recordings>(), [selected, setSelected] = useState('near_line_start'), [failed, setFailed] = useState(false), [attempt, setAttempt] = useState(0);
  const [mode, setMode] = useState<'cloud' | 'recorded'>('cloud');
  useEffect(() => { const controller = new AbortController(); setFailed(false); void loadRecordings(controller.signal).then(setData).catch(() => { if (!controller.signal.aborted) setFailed(true); }); return () => controller.abort(); }, [attempt]);
  const item = data?.cases.find(c => c.id === selected);
  return <section className="page synthetic-lab">
    <div className="eyebrow"><FlaskConical size={15}/> {text('СИНТЕТИЧЕСКАЯ ЛАБОРАТОРИЯ', 'SYNTHETIC LAB')}</div>
    <h1>{text('От наблюдения к точному моменту', 'From observation to an exact moment')}</h1>
    <p className="page-description">{text('Запустите Gemini на облачном сервере Render или исследуйте сохранённые ответы. Результат самой модели показан отдельно от измерения геометрии.', 'Run Gemini through the Render cloud server or explore recorded responses. The model result is shown separately from pixel geometry.')}</p>
    <div className="lab-scope"><ShieldCheck size={22}/><div><strong>{text('Только сгенерированные фигуры · бесплатные режимы', 'Generated shapes only · free modes')}</strong><p>{text('Это демонстрация направления и времени событий. Она не определяет нарушения банковских процедур и не принимает пользовательские видео.', 'This demonstrates event direction and timing. It does not detect bank-procedure violations or accept uploaded videos.')}</p></div></div>
    <div className="lab-mode" role="group" aria-label={text('Режим лаборатории', 'Laboratory mode')}>
      <button aria-pressed={mode === 'cloud'} onClick={() => setMode('cloud')}>{text('Облачный анализ', 'Cloud analysis')}</button>
      <button aria-pressed={mode === 'recorded'} onClick={() => setMode('recorded')}>{text('Записанные примеры', 'Recorded examples')}</button>
    </div>
    {mode === 'recorded' && <><div className="lab-metrics"><div><strong>8</strong><span>{text('синтетических сценариев', 'synthetic scenarios')}</span></div><div><strong>8/8</strong><span>{text('прошли повторную обработку записей', 'passed recorded-response replay')}</span></div><div><strong>3/8</strong><span>{text('завершено в архивном API-прогоне', 'completed in the archived API run')}</span></div><div><strong>$0</strong><span>{text('API-расходы записанного режима', 'API charges for recorded mode')}</span></div></div>
    <p className="lab-quota">{text('Архив Gemini 2.5 Flash: свежий прогон остановился на бесплатном лимите 20/20. В записанном режиме новые запросы Gemini не выполняются.', 'Gemini 2.5 Flash archive: the fresh run stopped at the free daily limit of 20/20. Recorded mode makes no new Gemini requests.')}</p></>}
    {failed && <div role="alert" className="notice">{text('Не удалось загрузить демонстрационные записи.', 'Could not load demo recordings.')} <button className="text-button" onClick={() => setAttempt(v => v + 1)}>{text('Повторить', 'Retry')}</button></div>}
    {!data && !failed && <p role="status">{text('Загрузка синтетических примеров…', 'Loading synthetic examples…')}</p>}
    {data && item && <div className="lab-workspace"><nav aria-label={text('Синтетические сценарии', 'Synthetic scenarios')} className="lab-scenarios">{data.cases.map((c, i) => <button key={c.id} aria-current={selected === c.id ? 'true' : undefined} onClick={() => setSelected(c.id)}><span className="lab-number">{String(i + 1).padStart(2, '0')}</span><span>{locale === 'en' ? c.title_en : c.title_ru}</span><Play size={14}/></button>)}</nav>
    {mode === 'cloud' ? <CloudSynthetic scenario={item.id} title={locale === 'en' ? item.title_en : item.title_ru} videoUrl={item.video_url} duration={item.duration_sec} sourceHash={item.video_sha256}/> : <RecordedCase key={item.id} item={item}/>}</div>}
  </section>;
}
