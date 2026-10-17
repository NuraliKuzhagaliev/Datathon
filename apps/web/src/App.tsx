import { LanguageSwitcher, useI18n } from './i18n';
import { useEffect, useState } from 'react';
import { FolderOpen, BookOpen, SlidersHorizontal, Plus, ArrowUpRight, ShieldCheck, Search, ChevronRight, FileVideo, Clock3, AlertTriangle, CircleCheck, LogOut, KeyRound, Monitor, Server, RefreshCw, FlaskConical, Trash2, ArrowRight, Network } from 'lucide-react';
import { HttpApi, errorText } from './api/client';
import type { ReviewApi, CaseSummary } from './api/types';
import { Brand, ErrorNotice, Loading, Modal, Tag } from './components/ui';
import { Upload } from './features/Upload';
import { Evidence } from './features/Evidence';
import { Rules } from './features/Rules';
import { QuickStart } from './features/QuickStart';
import { ThirdPartyNotices } from './features/ThirdPartyNotices';
import { useRequest } from './lib/useRequest';

type Page = 'cases' | 'rules' | 'system';
const statusLabel = (item: CaseSummary) => item.status === 'failed' ? 'Ошибка обработки' : item.status === 'processing' ? 'Обрабатывается' : item.verdict === 'violation' ? 'Требует проверки' : 'Признаков не обнаружено';
function readCase() { const hash = window.location.hash.slice(1); return hash.startsWith('case=') ? new URLSearchParams(hash).get('case') : null; }

function Connect({ connected, demo }: { connected: (api: ReviewApi) => void; demo?: () => void }) {
  const { t } = useI18n();
  const [key, setKey] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function connect(e: React.FormEvent) {
    e.preventDefault(); if (!key.trim() || busy) return; setBusy(true); setError('');
    const api = new HttpApi(key.trim());
    try { await api.list(); connected(api); setKey(''); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return <div className="connect-layout"><section className="connect-intro"><div className="eyebrow">{t("КАЖДОЕ НАБЛЮДЕНИЕ — ПРОВЕРЯЕМО")}</div><h1>{t("От момента на видео")}<br/>{t("к обоснованному")}<br/><span>{t("решению.")}</span></h1><p>{t("Рабочее место для проверки кассовых операций. Событие, контекст и источник нормы — в одном окне.")}</p><div className="connect-features"><span><EyeMark/>{t("Точные моменты")}</span><span><BookOpen size={19}/>{t("Проверяемые источники")}</span><span><ShieldCheck size={19}/>{t("Решение человека")}</span></div><div className="flow-preview" aria-hidden="true"><div className="flow-line"/><span><span className="flow-node"><FileVideo size={21}/></span>{t("Видеозапись")}</span><ArrowRight size={18}/><span><span className="flow-node accent"><Search size={21}/></span>{t("Доказательства")}</span><ArrowRight size={18}/><span><span className="flow-node"><CircleCheck size={21}/></span>{t("Проверка")}</span></div></section>
    <section className="connect-card"><span className="connect-symbol"><KeyRound size={24}/></span><h2>{t("Войти в рабочее пространство")}</h2><p className="muted">{t("Введите ключ оператора, предоставленный командой сервера.")}</p><form onSubmit={connect}><label className="field">{t("Ключ доступа")}<input type="password" autoComplete="off" spellCheck={false} value={key} onChange={e => setKey(e.target.value)} placeholder={t("Ваш API-ключ")} required/></label>{error && <ErrorNotice message={error}/>}<button className="button primary full" disabled={busy || !key.trim()}>{busy ? t("Подключение…") : t("Открыть рабочее пространство")}<ArrowRight size={18}/></button></form><p className="privacy-note"><ShieldCheck size={16}/>{t("Ключ хранится только в памяти текущего окна.")}</p>{demo && <div className="demo-entry"><span>{t("Посмотреть интерфейс без сервера")}</span><button className="text-button" onClick={demo}><FlaskConical size={16}/>{t("Открыть синтетическое демо")}</button></div>}</section>
  </div>;
}
function EyeMark() { return <Search size={19}/>; }

function Cases({ api, open, newAnalysis, guideExpanded, toggleGuide }: { api: ReviewApi; open: (id: string) => void; newAnalysis: () => void; guideExpanded: boolean; toggleGuide: () => void }) {
  const { t } = useI18n();
  const request = useRequest(signal => api.list(signal), [api], 5000); const [query, setQuery] = useState(''); const [filter, setFilter] = useState('all');
  const [deleting, setDeleting] = useState<CaseSummary>(); const [deleteBusy, setDeleteBusy] = useState(false); const [deleteError, setDeleteError] = useState('');
  const { locale } = useI18n();
  const content = (value: string) => api.synthetic ? api.demoText?.(value, locale) ?? value : value;
  const items = request.data?.items.filter(item => content(item.filename).toLocaleLowerCase().includes(query.toLocaleLowerCase()) && (filter === 'all' || (filter === 'attention' ? item.verdict === 'violation' : item.status === filter))) ?? [];
  async function remove() { if (!deleting || deleteBusy) return; setDeleteBusy(true); setDeleteError(''); try { await api.remove(deleting.job_id); setDeleting(undefined); request.retry(); } catch (e) { setDeleteError(errorText(e)); } finally { setDeleteBusy(false); } }
  return <section className="page"><div className="page-heading"><div><div className="eyebrow">{t("РАБОЧЕЕ ПРОСТРАНСТВО")}</div><h1>{t("Проверка операций")}</h1><p className="page-description">{t("Видео, доказательства и решения. Всё, что нужно для внимательной проверки.")}</p></div><button className="button primary" onClick={newAnalysis}><Plus size={18}/>{t("Новый анализ")}</button></div>
    <QuickStart expanded={guideExpanded} toggle={toggleGuide} synthetic={api.synthetic} start={api.synthetic ? () => { const example = request.data?.items.find(item => item.verdict === "violation") ?? request.data?.items[0]; if (example) open(example.job_id); else newAnalysis(); } : newAnalysis}/>
    <div className="section-toolbar"><div className="filter-tabs" role="group" aria-label={t("Фильтр дел")}>{[['all',t("Все дела")],['attention',t("Требуют проверки")],['processing',t("В обработке")]].map(([value,label]) => <button key={value} aria-pressed={filter === value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}</button>)}</div><label className="search"><Search size={17}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder={t("Поиск по имени файла")} aria-label={t("Поиск дел")}/></label><button className="icon-button" aria-label={t("Обновить список")} onClick={request.retry}><RefreshCw size={17}/></button></div>
    {request.error && <ErrorNotice message={request.error} retry={request.retry}/>}{request.loading && <Loading/>}
    {!!items.length && <div className="case-table"><div className="table-head"><span>{t("Видеозапись")}</span><span>{t("Результат")}</span><span>{t("Создано")}</span><span/></div>{items.map(item => <div className="case-row" key={item.job_id}><button className="case-open" onClick={() => open(item.job_id)}><span className="file-icon"><FileVideo size={22}/></span><span><strong>{content(item.filename)}</strong><small className="mono">{item.job_id}</small></span></button><div className="case-status"><Tag tone={item.status === 'failed' ? 'red' : item.status === 'processing' ? 'violet' : item.verdict === 'violation' ? 'amber' : 'mint'}>{item.status === 'processing' ? <Clock3 size={14}/> : item.verdict === 'no_violation' ? <CircleCheck size={14}/> : <AlertTriangle size={14}/>}{t(statusLabel(item))}</Tag></div><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(locale === 'en' ? 'en-GB' : 'ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</time><div className="row row-actions"><button className="icon-button" aria-label={t("Удалить дело {0}", [item.job_id])} onClick={() => { setDeleting(item); setDeleteError(''); }}><Trash2 size={15}/></button><button className="icon-button" aria-label={t("Открыть дело {0}", [item.job_id])} onClick={() => open(item.job_id)}><ChevronRight size={19}/></button></div></div>)}</div>}
    {!request.loading && !request.error && !items.length && <div className="empty"><FolderOpen size={36}/><h2>{query || filter !== 'all' ? t("Подходящих дел нет") : t("Первое дело начинается с видео")}</h2><p>{query || filter !== 'all' ? t("Измените поиск или фильтр.") : t("Загрузите MOV, чтобы получить результат с привязкой ко времени и доказательствами.")}</p>{!query && filter === 'all' && <button className="button secondary" onClick={newAnalysis}><Plus size={17}/>{t("Добавить видео")}</button>}</div>}
    <div className="list-footnote"><ShieldCheck size={16}/>{t("Выводы системы помогают проверяющему и не являются юридическим заключением.")}</div>
    {deleting && <Modal title={t("Удалить дело?")} close={() => { if (!deleteBusy) setDeleting(undefined); }}><p>{t("Дело «")}{content(deleting.filename)}{t("» и сохранённые материалы будут удалены на сервере. Это действие нельзя отменить.")}</p>{deleteError && <ErrorNotice message={deleteError}/>}<div className="modal-actions"><button className="button secondary" disabled={deleteBusy} onClick={() => setDeleting(undefined)}>{t("Отмена")}</button><button className="button destructive" disabled={deleteBusy} onClick={remove}>{deleteBusy ? t("Удаление…") : t("Удалить дело")}</button></div></Modal>}
  </section>;
}


function System({ api }: { api: ReviewApi }) {
  const { t } = useI18n();
  const health = useRequest(signal => api.health(signal), [api], 5000);
  return <section className="page"><div className="eyebrow">{t("ПОДКЛЮЧЕНИЕ И СРЕДА")}</div><h1>{t("Система")}</h1><p className="page-description">{t("Состояние сервиса по его фактическому ответу. Здесь нет предположений о готовности модели.")}</p>{health.error && <ErrorNotice message={health.error} retry={health.retry}/>}
    <div className="system-grid"><div className="system-card"><Server size={24}/><h2>{t("Сервис анализа")}</h2><Tag tone={health.data?.ready ? 'mint' : 'amber'}>{api.synthetic ? t("Синтетическое демо") : health.data?.ready ? t("Готов к обработке") : health.loading ? t("Проверяется…") : t("Не готов / недоступен")}</Tag><dl className="metadata"><div><dt>{t("Адрес интерфейса")}</dt><dd className="hash">{window.location.origin}</dd></div><div><dt>{t("Режим сервиса")}</dt><dd>{api.synthetic ? t("Модель не запущена") : health.data?.mode === 'offline' ? t("На этом компьютере") : health.data?.mode === 'server' ? t("Сервер команды") : t("Нет данных")}</dd></div><div><dt>{t("Контракт")}</dt><dd>{health.data?.contract_version ?? t("Не подтверждён")}</dd></div></dl><button className="button secondary" onClick={health.retry}><RefreshCw size={16}/>{t("Проверить соединение")}</button></div>
    <div className="system-card"><Monitor size={24}/><h2>{t("Среда запуска")}</h2><p>{window.cashproof ? t("Приложение Windows · общий интерфейс CashProof") : t("Веб-браузер · общий интерфейс CashProof")}</p><p className="muted">{t("Версии модели и норм указаны в каждом деле. Готовность сервиса показывается по ответу сервера; сведения о видеокарте и ресурсах модели здесь недоступны.")}</p><div className="notice"><Network size={18}/>{t("Автономность подтверждается отдельным запуском без сети на компьютере с подготовленными ресурсами.")}</div>{window.cashproof && <button className="button secondary" onClick={() => void window.cashproof?.showLauncher()}>{t("Выбрать режим подключения")}</button>}</div></div>
    <ThirdPartyNotices/>
  </section>;
}

export function App() {
  const { t } = useI18n();
  const [api, setApi] = useState<ReviewApi>(); const [page, setPage] = useState<Page>('cases'); const [caseId, setCaseId] = useState<string | null>(readCase());
  const [focusMode, setFocusMode] = useState(false); const [guideExpanded, setGuideExpanded] = useState(true);
  const [upload, setUpload] = useState(false); const [initError, setInitError] = useState('');
  async function demo() { const { createDemo } = await import('./mocks/demo'); setApi(createDemo()); }
  useEffect(() => {
    let alive = true;
    if (import.meta.env.DEV && new URLSearchParams(location.search).get('demo') === '1') void import('./mocks/demo').then(m => { if (alive) setApi(m.createDemo()); });
    else if (window.cashproof) void window.cashproof.getConfig().then(config => { if (alive && config.apiKey) setApi(new HttpApi(config.apiKey)); }).catch(() => { if (alive) setInitError('Не удалось получить настройки приложения. Вернитесь к выбору режима.'); });
    const change = () => setCaseId(readCase()); window.addEventListener('hashchange', change);
    return () => { alive = false; window.removeEventListener('hashchange', change); };
  }, []);
  useEffect(() => { setFocusMode(false); }, [api, caseId]);
  const health = useRequest(async signal => api ? api.health(signal) : null, [api], api ? 10000 : 0);
  function open(id: string) { setPage('cases'); location.hash = new URLSearchParams({ case: id }).toString(); setCaseId(id); }
  function navigate(next: Page) { setFocusMode(false); setPage(next); setCaseId(null); history.replaceState(null, '', location.pathname + location.search); }
  return <div className={`app-shell ${!api ? 'disconnected' : ''} ${focusMode && api && caseId ? 'focus-mode' : ''}`}><a className="skip-link" href="#main">{t("Перейти к содержимому")}</a><aside className="sidebar"><Brand/><div className="nav-label">{t("РАБОЧЕЕ МЕСТО")}</div><nav aria-label={t("Основная навигация")}>{([['cases',FolderOpen,t("Дела")],['rules',BookOpen,t("Библиотека норм")],['system',SlidersHorizontal,t("Система")]] as const).map(([value,Icon,label]) => <button key={value} aria-label={label} disabled={!api} aria-current={page === value && api ? 'page' : undefined} className={page === value && api ? 'active' : ''} onClick={() => navigate(value)}><Icon size={19}/><span>{label}</span>{page === value && api && <span className="nav-indicator"/>}</button>)}</nav><div className="sidebar-bottom"><div className="local-note"><ShieldCheck size={21}/><strong>{t("Проверяемые выводы")}</strong><p>{t("Каждое событие связано с кадром, временем и источником.")}</p></div><div className="workspace-label"><span className="workspace-avatar">CP</span><span>CashProof<small>{t("Команда хакатона")}</small></span></div></div></aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb">{t("Рабочее пространство ")}<ChevronRight size={14}/><strong>{!api ? t("Подключение") : caseId ? t("Проверка дела") : page === 'cases' ? t("Дела") : page === 'rules' ? t("Библиотека норм") : t("Система")}</strong></div><div className="topbar-right"><LanguageSwitcher/><span className={`connection ${api?.synthetic ? 'amber' : health.data?.ready ? 'mint' : ''}`}><span className="state-dot"/>{api?.synthetic ? t("Демонстрация") : health.data?.ready ? health.data.mode === 'offline' ? t("Локальный сервис готов") : t("Сервер готов") : api ? t("Сервис не готов") : t("Нет подключения")}</span>{api && <button className="icon-button" aria-label={t("Отключиться")} onClick={() => { setApi(undefined); navigate('cases'); }}><LogOut size={17}/></button>}</div></header>
    {api?.synthetic && <div className="synthetic-bar"><FlaskConical size={16}/><strong>{t("Синтетическое демо")}</strong><span>{t("Примеры интерфейса. Модель не выполнялась; решения сохраняются только в памяти.")}</span></div>}
    <main id="main">{initError && <ErrorNotice message={initError}/>}<AppErrorBoundary>{!api ? <Connect connected={setApi} demo={import.meta.env.DEV ? demo : undefined}/> : page === 'rules' ? <Rules api={api}/> : page === 'system' ? <System api={api}/> : caseId ? <Evidence key={caseId} api={api} id={caseId} focused={focusMode} setFocused={setFocusMode} back={() => navigate('cases')} newAnalysis={() => setUpload(true)}/> : <Cases api={api} open={open} newAnalysis={() => setUpload(true)} guideExpanded={guideExpanded} toggleGuide={() => setGuideExpanded(v => !v)}/>}</AppErrorBoundary></main>
    <footer className="app-footer"><span>CashProof <span className="muted">/</span>{t(" Проверка операций")}</span><span>{t("Наблюдение → доказательство → решение ")}<ArrowUpRight size={13}/></span></footer></div>
    {upload && api && <Upload api={api} close={() => setUpload(false)} accepted={id => { setUpload(false); open(id); }}/>}
  </div>;
}

import { Component, type ReactNode } from 'react';
class AppErrorBoundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <div className="page"><ErrorNotice message="Не удалось отобразить данные. Обновите страницу и переподключитесь."/></div> : this.props.children; }
}
