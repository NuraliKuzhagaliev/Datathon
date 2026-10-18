import { useI18n } from '../i18n';
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Download, ChevronLeft, ChevronRight, Play, Pause, Repeat2, Maximize2, Minimize2, Keyboard, FileCheck2, CircleCheck, CircleX, CircleHelp, BookOpen, AlertTriangle, Eye, Clock3, ShieldCheck, Film, Image as ImageIcon, Info } from 'lucide-react';
import type { CaseDetail, UiEvent, ReviewApi, ReviewInput } from '../api/types';
import { errorText } from '../api/client';
import { useRequest } from '../lib/useRequest';
import { mapTime, mappedInterval, time } from '../lib/time';
import { ErrorNotice, Loading, Modal, Tag } from '../components/ui';
import { RuleDrawer } from './Rules';
import { useReviewDrafts } from './ReviewDrafts';

const stages = { queued: 'В очереди', decoding: 'Подготовка видео', screening: 'Просмотр видеоряда', verifying: 'Проверка наблюдений', packaging: 'Подготовка доказательств', complete: 'Завершено', failed: 'Ошибка обработки' };
const decisions = { unreviewed: 'Не проверено', confirmed: 'Подтверждено проверяющим', dismissed: 'Отклонено проверяющим', uncertain: 'Нужна дополнительная проверка' };

function ReviewForm({ api, job, event }: { api: ReviewApi; job: string; event: UiEvent }) {
  const { t, locale } = useI18n();
  const drafts = useReviewDrafts();
  const draft = drafts.read(job, event); const { decision, note } = draft.input;
  const dirty = drafts.changed(draft);
  const setDecision = (value: ReviewInput['decision']) => drafts.edit(job, event, { decision: value, note });
  const setNote = (value: string) => drafts.edit(job, event, { decision, note: value });
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [error, setError] = useState(''); const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function save() {
    if (busy) return;
    const controller = new AbortController(); active.current = controller; setBusy(true); setError(''); setMessage('');
    try {
      const saved = await api.review(job, event.event_id, { decision, note }, controller.signal);
      if (saved.event_id !== event.event_id) throw new Error('Сервер подтвердил решение для другого события. Повторите сохранение.');
      if (!controller.signal.aborted) { drafts.acknowledge(job, saved); setMessage(api.synthetic ? 'Сохранено в памяти демо. Исходный результат не изменён.' : 'Решение сохранено. Исходный результат модели не изменён.'); }
    }
    catch (e) { if (!controller.signal.aborted) setError(errorText(e)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <div className="review-form"><h3><FileCheck2 size={17}/>{t("Решение проверяющего")}</h3><p className="muted small">{t("Ваша оценка хранится отдельно от вывода модели.")}</p>
    <div className="decision-group" role="group" aria-label={t("Решение проверяющего")}>{([['confirmed', CircleCheck, t("Подтвердить")], ['dismissed', CircleX, t("Отклонить")], ['uncertain', CircleHelp, t("Не уверен")]] as const).map(([value, Icon, label]) => <button key={value} aria-pressed={decision === value} disabled={busy} className={decision === value ? 'selected' : ''} onClick={() => { setDecision(value); setMessage(''); }}><Icon size={17}/>{label}</button>)}</div>
    <details className="note-details"><summary>{t("Заметка проверяющего")}{note ? t(" · есть текст") : t(" · добавить")}</summary><label className="field">{t("Заметка")}<textarea aria-label={t("Заметка")} rows={3} maxLength={2000} disabled={busy} value={note} onChange={e => { setNote(e.target.value); setMessage(''); }} placeholder={t("Что помогло принять решение?")}/></label></details>
    <p className={`draft-status small ${dirty ? 'amber' : 'muted'}`} aria-live="polite">{dirty ? t("Черновик не сохранён. Переключение дел и событий сохраняет его в этом сеансе; перед выходом сохраните решение. В ZIP попадут только сохранённые решения.") : draft.saved.updated_at ? t("Сохранено: {0}", [new Date(draft.saved.updated_at).toLocaleString(locale === 'en' ? 'en-GB' : 'ru-RU')]) : t("Решение ещё не сохранено.")}</p>
    <div className="row"><small className="muted">{note.length} / 2000</small><button className="button primary compact" disabled={busy} onClick={save}>{busy ? t("Сохранение…") : t("Сохранить решение")}</button></div>
    {error && <ErrorNotice message={error}/>}<p role="status" className="save-message">{t(message)}</p>
  </div>;
}

function Stage({ data, retry }: { data: CaseDetail; retry: () => void }) {
  const { t } = useI18n();
  if (data.status === 'failed') return <div className="state-card"><div className="state-symbol danger"><AlertTriangle size={30}/></div><h2>{t("Анализ не завершён")}</h2><p>{t("Это технический сбой, а не результат «нарушений нет».")}</p><ErrorNotice message={data.error?.code === 'DECODE_FAILED' ? t("Не удалось прочитать видео. Проверьте файл и попробуйте загрузить его заново.") : t("Обработчик завершился с ошибкой. Проверьте состояние сервера.")}/><code>{data.error?.code}</code><button className="button secondary" onClick={retry}>{t("Обновить статус")}</button></div>;
  return <div className="state-card"><div className="state-symbol"><ScanProgress/></div><div className="eyebrow">{t("АНАЛИЗ ВЫПОЛНЯЕТСЯ")}</div><h2>{t(stages[data.stage])}</h2><p>{t("Система обрабатывает видеоряд и проверяет возможные события.")}</p><div className="stage-list">{(['queued','decoding','screening','verifying','packaging'] as const).map((s, i) => <div className={s === data.stage ? 'active' : ''} key={s}><span>{String(i + 1).padStart(2, '0')}</span>{t(stages[s])}</div>)}</div><progress aria-label={t("Прогресс анализа")} max="100" {...(data.progress_percent === null ? {} : { value: data.progress_percent })}/><div className="row"><span>{data.progress_percent === null ? t("Процент этапа пока неизвестен") : `${data.progress_percent}%`}</span><span className="mono">{time(data.elapsed_sec)}{t(" прошло")}</span></div><p className="small muted">{t("Можно вернуться к списку дел. Принятый сервером анализ продолжится.")}</p></div>;
}
function ScanProgress() { return <Film size={30}/>; }

export function Evidence({ api, id, back, newAnalysis, focused, setFocused }: { api: ReviewApi; id: string; back: () => void; newAnalysis: () => void; focused: boolean; setFocused: (value: boolean) => void }) {
  const { t } = useI18n();
  const drafts = useReviewDrafts();
  const { locale } = useI18n();
  const content = (value: string) => api.synthetic ? api.demoText?.(value, locale) ?? value : value;
  const frameImage = (value: string) => api.synthetic ? api.demoImage?.(value, locale) ?? value : value;
  const previous = useRef<CaseDetail | null>(null);
  const request = useRequest(async signal => {
    const next = await api.case(id, signal);
    if (next.job_id !== id) throw new Error('Сервер вернул другое дело. Обновите соединение.');
    const old = previous.current;
    if (old?.job_id === id) {
      const order = ['queued', 'decoding', 'screening', 'verifying', 'packaging', 'complete'];
      if (old.status !== 'processing' && next.status !== old.status) throw new Error('Сервер изменил окончательный статус дела.');
      if (old.status === 'processing' && next.status === 'processing' && order.indexOf(next.stage) < order.indexOf(old.stage)) throw new Error('Сервер вернул устаревший этап обработки.');
      if (old.status === 'done' && JSON.stringify(old.model_result) !== JSON.stringify(next.model_result)) throw new Error('Исходный результат завершённого анализа изменился.');
      if (old.status === 'done' && JSON.stringify(old.rules) !== JSON.stringify(next.rules)) throw new Error('Снимок источников завершённого дела изменился.');
    }
    if (!signal.aborted) previous.current = next;
    return next;
  }, [api, id], 2500);
  const [selected, setSelected] = useState(0); const [frame, setFrame] = useState(0); const [tab, setTab] = useState<'observation' | 'context'>('observation');
  const [ruleOpen, setRuleOpen] = useState(false); const [zoom, setZoom] = useState(false); const [mediaMode, setMediaMode] = useState<'frame' | 'video'>('frame');
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const focusButton = useRef<HTMLButtonElement>(null);
  const [mediaUrl, setMediaUrl] = useState(''); const [mediaError, setMediaError] = useState(''); const [mediaRetry, setMediaRetry] = useState(0);
  const [playing, setPlaying] = useState(false); const [looping, setLooping] = useState(false); const [cursor, setCursor] = useState(0); const [notice, setNotice] = useState('');
  const [exporting, setExporting] = useState(false); const video = useRef<HTMLVideoElement>(null); const exportController = useRef<AbortController | null>(null);
  const data = request.data; const event = data?.events[selected]; const evidence = event?.evidence_frames[frame];
  useEffect(() => () => exportController.current?.abort(), []);
  useEffect(() => { if (mediaMode === 'frame') video.current?.pause(); }, [mediaMode]);
  useEffect(() => {
    setMediaUrl(''); setMediaError('');
    if (!data?.media_ready) return;
    const controller = new AbortController(); let url = '';
    void api.blob(id, 'media', controller.signal).then(blob => { if (!controller.signal.aborted) { url = URL.createObjectURL(blob); setMediaUrl(url); } }).catch(e => { if (!controller.signal.aborted) setMediaError(errorText(e)); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [api, id, data?.media_ready, mediaRetry]);
  useEffect(() => { setSelected(0); setFrame(0); setLooping(false); setNotice(''); }, [id]);
  useEffect(() => {
    if (!event) return;
    setCursor(event.timecode_sec);
    setFrame(event.evidence_frames.reduce((best, f, index, frames) => Math.abs(f.timestamp_sec - event.timecode_sec) < Math.abs(frames[best].timestamp_sec - event.timecode_sec) ? index : best, 0));
    setLooping(false);
    const mapped = mapTime(event.timecode_sec, data?.time_map ?? []);
    if (video.current && mapped !== null) video.current.currentTime = mapped;
  }, [event?.event_id]);
  function select(index: number) { setSelected(Math.max(0, Math.min((data?.events.length ?? 1) - 1, index))); setMediaMode('frame'); }
  useEffect(() => {
    function key(e: KeyboardEvent) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.isComposing || e.repeat || document.querySelector('dialog[open]')) return;
      if (e.key === 'Escape' && focused) { e.preventDefault(); setFocused(false); focusButton.current?.focus(); return; }
      if (e.target instanceof HTMLElement && (e.target.closest('input,textarea,select,[role="textbox"]') || e.target.isContentEditable)) return;
      if (data?.status !== 'done') return;
      if (e.code === 'KeyJ' || e.key.toLowerCase() === 'j') { e.preventDefault(); select(selected + 1); }
      if (e.code === 'KeyK' || e.key.toLowerCase() === 'k') { e.preventDefault(); select(selected - 1); }
      if (e.code === 'KeyF' || e.key.toLowerCase() === 'f') { e.preventDefault(); setFocused(!focused); focusButton.current?.focus(); }
      if (e.key === '?') { e.preventDefault(); setShortcutsOpen(true); }
    }
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  }, [selected, data?.events.length, data?.status, focused, setFocused]);
  function seek(source: number) {
    const mapped = mapTime(source, data?.time_map ?? []);
    if (mapped === null) { setNotice('Для этого момента отсутствует соответствие времени видеопросмотра.'); return; }
    setCursor(source);
    if (video.current) video.current.currentTime = mapped;
  }
  async function replay() {
    if (!event || !data || !mediaUrl) return;
    if (!mappedInterval(event.context_start_sec, event.context_end_sec, data.time_map)) { setNotice('Сервер не предоставил карту времени для всего контекста.'); return; }
    setMediaMode('video'); setLooping(true); seek(event.context_start_sec);
    try { await video.current?.play(); } catch { setNotice('Нажмите воспроизведение после загрузки видео.'); }
  }
  async function exportBundle() {
    if (exporting) return;
    const controller = new AbortController(); exportController.current = controller; setExporting(true); setNotice('');
    try { const blob = await api.blob(id, 'bundle', controller.signal); if (controller.signal.aborted) return; const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `cashproof-${id.replace(/[^a-zA-Z0-9_-]/g, '_')}.zip`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000); setNotice('ZIP получен от сервера и передан браузеру для сохранения.'); }
    catch (e) { if (!controller.signal.aborted) setNotice(errorText(e)); }
    finally { if (!controller.signal.aborted) setExporting(false); }
  }
  if (!data) return <section className="page"><button className="text-button" onClick={back}><ArrowLeft size={17}/>{t("Все дела")}</button>{request.loading ? <Loading/> : <ErrorNotice message={request.error ?? t("Дело недоступно")} retry={request.retry}/>}</section>;
  const positive = data.model_result?.verdict === 'violation';
  return <section className="evidence-page">
    <div className="case-top"><button className="text-button" onClick={back}><ArrowLeft size={16}/>{t("Все дела")}</button><span className="divider-slash">/</span><span className="filename" title={content(data.filename)}>{content(data.filename)}</span><span className="case-id mono">{id}</span></div>
    <div className="result-heading"><div><div className="eyebrow">{data.status === 'done' ? t("РЕЗУЛЬТАТ АНАЛИЗА") : t("ОБРАБОТКА ВИДЕО")}</div><h1 className={positive ? 'result-positive' : ''}>{data.status === 'done' ? positive ? t("Обнаружены признаки возможных нарушений") : t("Нарушение не обнаружено") : t(stages[data.stage])}</h1><p>{t("Вспомогательная проверка по видимым действиям. Окончательная оценка — за человеком.")}</p></div><button className="button secondary" disabled={data.status !== 'done' || exporting} onClick={exportBundle}><Download size={17}/>{exporting ? t("Получение ZIP…") : t("Экспорт дела")}</button></div>
    {data.status === 'done' && <div className="evidence-tools" aria-label={t("Настройки просмотра")}>
      <button ref={focusButton} className={`button secondary compact ${focused ? 'focus-active' : ''}`} aria-pressed={focused} aria-keyshortcuts="f" onClick={() => setFocused(!focused)}>{focused ? <Minimize2 size={16}/> : <Maximize2 size={16}/>} {focused ? t("Обычный вид") : t("Сосредоточенная проверка")}</button>
      <span className="focus-hint">{focused ? t("Больше места для видео · Esc — вернуться") : t("Видео, контекст и решение в одном окне")}</span>
      <button className="text-button shortcuts-button" aria-keyshortcuts="Shift+/" onClick={() => setShortcutsOpen(true)}><Keyboard size={17}/>{t("Горячие клавиши")}</button>
    </div>}
    {request.error && <ErrorNotice message={request.error} retry={request.retry}/>}{notice && <div className="notice" role="status"><Info size={18}/>{t(notice)}</div>}
    {data.status !== 'done' ? <><Stage data={data} retry={request.retry}/>{data.status === 'failed' && <button className="button primary" onClick={newAnalysis}>{t("Загрузить другое видео")}</button>}</> : <>
    <div className="desk">
      <aside className="event-rail"><div className="panel-heading"><span>{t("События")}</span><span className="count">{data.events.length}</span></div><div className="event-list">{data.events.map((item, index) => <button key={item.event_id} className={`event-card ${index === selected ? 'active' : ''}`} aria-pressed={selected === index} onClick={() => select(index)}><span className="row"><span className="mono event-time">{time(item.timecode_sec)}</span><span className="event-index">{String(index + 1).padStart(2, '0')}</span></span><strong>{content(item.type)}</strong><span className="event-state"><span className={`state-dot ${drafts.read(id, item).saved.decision === 'unreviewed' ? 'amber' : 'mint'}`}/>{drafts.changed(drafts.read(id, item)) ? t('Есть несохранённый черновик') : t(decisions[drafts.read(id, item).saved.decision])}</span></button>)}</div>
      {!data.events.length && <div className="rail-empty"><CircleCheck size={26}/><p>{t("Поддерживаемых событий не найдено")}</p></div>}
      <div className="rail-bottom"><kbd>J</kbd><kbd>K</kbd><span>{t("следующее / предыдущее")}</span></div></aside>
      <div className="media-panel"><div className="panel-heading"><span><Eye size={16}/>{t("Материалы дела")}</span><div className="segmented"><button aria-pressed={mediaMode === 'frame'} onClick={() => setMediaMode('frame')}><ImageIcon size={14}/>{t("Кадр")}</button><button aria-pressed={mediaMode === 'video'} disabled={!mediaUrl} onClick={() => setMediaMode('video')}><Film size={14}/>{t("Видео")}</button></div></div>
        <div className="evidence-stage">
          {evidence && mediaMode === 'frame' ? <><img className="original-frame" src={`data:image/jpeg;base64,${frameImage(evidence.image_base64)}`} alt={t("Доказательство события {0}, {1}", [selected + 1, time(evidence.timestamp_sec)])}/><div className="stage-label"><span className="state-dot mint"/>{data.is_synthetic ? t("Синтетический кадр") : t("Исходный кадр")}<span className="mono">{time(evidence.timestamp_sec)}</span></div><button className="zoom-button icon-button" onClick={() => setZoom(true)} aria-label={t("Увеличить кадр")}><Maximize2 size={17}/></button></> : !mediaUrl && <div className="media-placeholder"><ShieldCheck size={42}/><strong>{positive ? t("Выберите событие") : t("Видимые признаки не обнаружены")}</strong><p>{positive ? t("Откройте кадр из списка событий.") : t("Это результат в пределах проверенных норм и доступной видимости.")}</p></div>}
          {mediaUrl && <video ref={video} className={`original-video ${mediaMode === 'video' ? '' : 'hidden-video'}`} src={mediaUrl} muted playsInline preload="metadata" onLoadedMetadata={() => seek(cursor)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onError={() => setMediaError('Не удалось воспроизвести MP4. Проверьте формат видео для просмотра на сервере.')} onTimeUpdate={() => { if (!video.current) return; const t = mapTime(video.current.currentTime, data.time_map, true); if (t !== null) { setCursor(t); if (looping && event && t >= event.context_end_sec) seek(event.context_start_sec); } }} aria-label={t("Видеозапись операции")}/>}
        </div>
        {mediaError && <ErrorNotice message={mediaError} retry={() => setMediaRetry(v => v + 1)}/>}
        <div className="player-bar"><button className="icon-button" disabled={!mediaUrl || !data.time_map.length} aria-label={playing ? t("Пауза") : t("Воспроизвести")} onClick={() => { setMediaMode('video'); if (playing) video.current?.pause(); else void video.current?.play().catch(() => setNotice('Видео пока недоступно для воспроизведения.')); }}>{playing ? <Pause size={18}/> : <Play size={18}/>}</button><span className="mono">{time(mediaMode === 'frame' ? evidence?.timestamp_sec ?? cursor : cursor)} <span className="muted">/ {data.duration_sec === null ? '—' : time(data.duration_sec)}</span></span><button className={`text-button context-button ${looping ? 'accent' : ''}`} disabled={!mediaUrl || !event} onClick={looping ? () => setLooping(false) : replay}><Repeat2 size={16}/>{looping ? t("Повтор включён") : t("Контекст")}</button></div>
        <div className="timeline"><input type="range" aria-label={t("Позиция в исходном видео")} min={0} max={data.duration_sec || 1} step={0.1} value={cursor} disabled={!mediaUrl || !data.time_map.length} onChange={e => { setMediaMode('video'); setLooping(false); seek(Number(e.target.value)); }}/><div className="coverage-track" aria-label={t("Покрытие анализа")}>{data.coverage.map((segment, index) => <span key={index} className={segment.state} style={{ left: `${segment.start_sec / (data.duration_sec || 1) * 100}%`, width: `${(segment.end_sec - segment.start_sec) / (data.duration_sec || 1) * 100}%` }} title={`${time(segment.start_sec)}–${time(segment.end_sec)}: ${segment.state === 'assessed' ? t("Оценено") : segment.state === 'limited' ? t("Ограниченная видимость") : t("Не оценено")} ${content(segment.reason ?? '')}`}/>)}</div><div className="timeline-labels"><span>00:00</span><span>{t("Исходное время")}</span><span>{data.duration_sec === null ? '—' : time(data.duration_sec)}</span></div></div>
        {event && <div className="storyboard">{event.evidence_frames.map((f, index) => <button key={`${index}-${f.timestamp_sec}`} aria-pressed={frame === index && mediaMode === 'frame'} onClick={() => { setFrame(index); setMediaMode('frame'); setCursor(f.timestamp_sec); }}><img src={`data:image/jpeg;base64,${frameImage(f.image_base64)}`} alt={t("Кадр {0}", [time(f.timestamp_sec)])}/><span>{f.timestamp_sec < event.timecode_sec ? t("До") : f.timestamp_sec > event.timecode_sec ? t("После") : t("Событие")}<b className="mono">{time(f.timestamp_sec)}</b></span></button>)}</div>}
        {!data.media_ready && <p className="media-footnote"><Info size={15}/>{data.is_synthetic ? t("Демо содержит только синтетические кадры. Видео и повтор контекста доступны после подключения сервера.") : t("Видео для просмотра ещё не готово. Кадры доказательств доступны отдельно.")}</p>}
      </div>
      <aside className="detail-panel">{event ? <><div className="panel-heading"><span>{t("Проверка события")}</span><div className="row"><button className="icon-button" disabled={selected === 0} onClick={() => select(selected - 1)} aria-label={t("Предыдущее событие")}><ChevronLeft size={17}/></button><button className="icon-button" disabled={selected >= data.events.length - 1} onClick={() => select(selected + 1)} aria-label={t("Следующее событие")}><ChevronRight size={17}/></button></div></div>
        <div className="detail-body"><div className="detail-tabs" role="tablist" aria-label={t("Сведения о событии")}><button role="tab" aria-selected={tab === 'observation'} onClick={() => setTab('observation')}>{t("Наблюдение")}</button><button role="tab" aria-selected={tab === 'context'} onClick={() => setTab('context')}>{t("Контекст и пределы")}</button></div>
        <div className="observation" role="tabpanel">{tab === 'observation' ? <><h3>{content(event.type)}</h3><p>{content(event.observation)}</p><div className="rationale"><span className="eyebrow">{t("ПОЧЕМУ НУЖНА ПРОВЕРКА")}</span><p>{content(event.rationale)}</p></div></> : <><h3>{t("Ограничения наблюдения")}</h3>{event.limitations.length ? <ul className="limits">{event.limitations.map((s, i) => <li key={i}>{content(s)}</li>)}</ul> : <p className="muted">{t("Сервер не указал ограничения. Это не доказывает полную видимость.")}</p>}<h3>{t("Противоречащие наблюдения")}</h3>{event.counterevidence.length ? <ul>{event.counterevidence.map((s, i) => <li key={i}>{content(s)}</li>)}</ul> : <p className="muted">{t("Отдельные контраргументы не переданы.")}</p>}</>}</div>
        <button className="source-card" onClick={() => setRuleOpen(true)}><BookOpen size={20}/><span><small>{t("ОСНОВАНИЕ")}</small><strong>{content(data.rules.find(r => event.rule_ids.includes(r.rule_id))?.display_name ?? t("Источник не передан"))}</strong><span>{t("Норма, редакция и применимость")}</span></span><ChevronRight size={18}/></button>
        <ReviewForm key={`${id}-${event.event_id}`} api={api} job={id} event={event}/></div>
      </> : <div className="negative-detail"><CircleCheck size={32}/><h3>{t("Нарушение не обнаружено")}</h3><p>{t("В рамках выполненной проверки система не нашла поддерживаемых видимых признаков.")}</p><p className="muted">{t("Результат не подтверждает соблюдение всех процедур банка. Учитывайте покрытие и видимость.")}</p><Tag tone="mint">{data.is_synthetic ? t("Учебный результат") : t("Автоматический результат")}</Tag></div>}</aside>
    </div>
    <div className="case-footer"><span><Clock3 size={14}/>{t("Обработка: ")}{time(data.elapsed_sec)}</span><span>{t("Модель: ")}{data.is_synthetic ? t("не запускалась") : data.model_version}</span><span>{t("Нормы: ")}{data.is_synthetic ? t("учебный пример") : data.rule_registry_version}</span></div>
    <details className="coverage-details"><summary>{t("Покрытие и дополнительные наблюдения")}</summary>{data.coverage.length ? data.coverage.map((s, i) => <p key={i}><span className="mono">{time(s.start_sec)}–{time(s.end_sec)}</span> · {s.state === 'assessed' ? t("Оценено") : s.state === 'limited' ? t("Ограничено") : t("Не оценено")}{s.reason ? ` · ${content(s.reason)}` : ''}</p>) : <p>{t("Сведения о покрытии не переданы сервером.")}</p>}{data.review_cues.map(cue => <div key={cue.cue_id}><strong>{time(cue.timecode_sec)}{t(" · Наблюдение вне вердикта")}</strong><p>{content(cue.reason)}</p><ul>{cue.limitations.map((t,i) => <li key={i}>{content(t)}</li>)}</ul></div>)}{data.input_sha256 && <p className="hash">SHA-256: {data.input_sha256}</p>}</details>
    </>}
    {shortcutsOpen && <Modal title={t("Горячие клавиши")} close={() => setShortcutsOpen(false)}>
      <p className="muted small">{t("Команды работают вне полей ввода и диалогов. Буквенные клавиши доступны и в русской раскладке.")}</p>
      <dl className="shortcut-list"><div><dt><kbd>J</kbd> / <kbd>{t("О")}</kbd></dt><dd>{t("Следующее событие")}</dd></div><div><dt><kbd>K</kbd> / <kbd>{t("Л")}</kbd></dt><dd>{t("Предыдущее событие")}</dd></div><div><dt><kbd>F</kbd> / <kbd>{t("А")}</kbd></dt><dd>{t("Переключить сосредоточенную проверку")}</dd></div><div><dt><kbd>Esc</kbd></dt><dd>{t("Закрыть диалог; затем вернуться к обычному виду")}</dd></div><div><dt><kbd>?</kbd></dt><dd>{t("Открыть эту подсказку")}</dd></div></dl>
      <p className="muted small">{t("Переключение вида сохраняет выбранное событие и текст заметки. Решение записывается кнопкой «Сохранить решение».")}</p>
    </Modal>}
    {ruleOpen && event && <RuleDrawer format={content} rules={data.rules.filter(r => event.rule_ids.includes(r.rule_id))} close={() => setRuleOpen(false)}/>}
    {zoom && evidence && <Modal title={`${data.is_synthetic ? t("Синтетический кадр") : t("Исходный кадр")} · ${time(evidence.timestamp_sec)}`} close={() => setZoom(false)} wide><img className="zoom-image" src={`data:image/jpeg;base64,${frameImage(evidence.image_base64)}`} alt={t("Увеличенный кадр доказательства")}/></Modal>}
  </section>;
}
