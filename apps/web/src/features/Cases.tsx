import { useState } from 'react';
import { AlertTriangle, CircleCheck, ChevronRight, Clock3, FileVideo, FolderOpen, Plus, RefreshCw, Search, ShieldCheck, Trash2 } from 'lucide-react';
import type { CaseSummary, ReviewApi } from '../api/types';
import { errorText } from '../api/client';
import { ErrorNotice, Loading, Modal, Tag } from '../components/ui';
import { useI18n } from '../i18n';
import { useRequest } from '../lib/useRequest';
import { QuickStart } from './QuickStart';
import { useReviewDrafts } from './ReviewDrafts';

type Filter = 'all' | 'attention' | 'processing' | 'negative' | 'failed';
const matches = (item: CaseSummary, filter: Filter) => filter === 'all' || (filter === 'attention' ? item.verdict === 'violation' : filter === 'negative' ? item.verdict === 'no_violation' : item.status === filter);
const statusLabel = (item: CaseSummary) => item.status === 'failed' ? 'Ошибка обработки' : item.status === 'processing' ? 'Обрабатывается' : item.verdict === 'violation' ? 'Требует проверки' : 'Признаков не обнаружено';

export function Cases({ api, open, newAnalysis, guideExpanded, toggleGuide }: { api: ReviewApi; open: (id: string) => void; newAnalysis: () => void; guideExpanded: boolean; toggleGuide: () => void }) {
  const { t, locale } = useI18n();
  const drafts = useReviewDrafts();
  const request = useRequest(signal => api.list(signal), [api], 5000);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [sort, setSort] = useState('newest');
  const [deleting, setDeleting] = useState<CaseSummary>();
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const content = (value: string) => api.synthetic ? api.demoText?.(value, locale) ?? value : value;
  const all = request.data?.items ?? [];
  const search = query.trim().toLocaleLowerCase();
  const items = all.filter(item => matches(item, filter) && `${content(item.filename)} ${item.job_id}`.toLocaleLowerCase().includes(search)).sort((a, b) => {
    const comparison = sort === 'name' ? content(a.filename).localeCompare(content(b.filename), locale, { numeric: true }) : (Date.parse(a.created_at) - Date.parse(b.created_at)) * (sort === 'oldest' ? 1 : -1);
    return comparison || a.job_id.localeCompare(b.job_id);
  });
  const filters = [
    ['all', t('Все дела'), FolderOpen, ''],
    ['attention', t('Требуют проверки'), AlertTriangle, 'amber'],
    ['processing', t('В обработке'), Clock3, 'violet'],
    ['negative', t('Без признаков'), CircleCheck, 'mint'],
    ['failed', t('Ошибки обработки'), AlertTriangle, 'red'],
  ] as const;
  async function remove() {
    if (!deleting || deleteBusy) return;
    setDeleteBusy(true); setDeleteError('');
    try { await api.remove(deleting.job_id); drafts.forget(deleting.job_id); setDeleting(undefined); request.retry(); }
    catch (error) { setDeleteError(errorText(error)); }
    finally { setDeleteBusy(false); }
  }
  return <section className="page">
    <div className="page-heading"><div><div className="eyebrow">{t('РАБОЧЕЕ ПРОСТРАНСТВО')}</div><h1>{t('Проверка операций')}</h1><p className="page-description">{t('Видео, доказательства и решения. Всё, что нужно для внимательной проверки.')}</p></div><button className="button primary" onClick={newAnalysis}><Plus size={18}/>{t('Новый анализ')}</button></div>
    <QuickStart expanded={guideExpanded} toggle={toggleGuide} synthetic={api.synthetic} start={api.synthetic ? () => { const example = all.find(item => item.verdict === 'violation') ?? all[0]; if (example) open(example.job_id); else newAnalysis(); } : newAnalysis}/>
    <div className="case-overview" role="group" aria-label={t('Фильтр дел')}>
      {filters.map(([value, label, Icon, tone]) => <button key={value} className={`overview-item ${tone}`} aria-label={label} aria-pressed={filter === value} onClick={() => setFilter(value)}><span><Icon size={16}/>{label}</span><strong>{request.data ? all.filter(item => matches(item, value)).length : '—'}</strong></button>)}
    </div>
    <div className="section-toolbar case-controls">
      <label className="search"><Search size={17}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder={t('Имя файла или ID дела')} aria-label={t('Поиск дел')}/></label>
      <label className="case-sort">{t('Порядок')}<select aria-label={t('Порядок дел')} value={sort} onChange={event => setSort(event.target.value)}><option value="newest">{t('Сначала новые')}</option><option value="oldest">{t('Сначала старые')}</option><option value="name">{t('По имени файла')}</option></select></label>
      <button className="icon-button" aria-label={t('Обновить список')} onClick={request.retry}><RefreshCw size={17}/></button>
    </div>
    {request.data && <div className="case-results-info"><span role="status">{t('Показано: {0} из {1}', [items.length, all.length])}</span>{(query || filter !== 'all') && <button className="text-button" onClick={() => { setQuery(''); setFilter('all'); }}>{t('Сбросить поиск и фильтр')}</button>}</div>}
    {request.error && <><ErrorNotice message={request.error} retry={request.retry}/>{request.data && <p className="small amber">{t('Показан последний полученный список. Он обновится после восстановления связи.')}</p>}</>}
    {request.loading && <Loading/>}
    {!!items.length && <div className="case-table"><div className="table-head"><span>{t('Видеозапись')}</span><span>{t('Результат')}</span><span>{t('Создано')}</span><span/></div>{items.map(item => <div className="case-row" key={item.job_id}>
      <button className="case-open" onClick={() => open(item.job_id)}><span className="file-icon"><FileVideo size={22}/></span><span><strong>{content(item.filename)}</strong><small className="mono">{item.job_id}</small></span></button>
      <div className="case-status"><Tag tone={item.status === 'failed' ? 'red' : item.status === 'processing' ? 'violet' : item.verdict === 'violation' ? 'amber' : 'mint'}>{item.status === 'processing' ? <Clock3 size={14}/> : item.verdict === 'no_violation' ? <CircleCheck size={14}/> : <AlertTriangle size={14}/>}{t(statusLabel(item))}</Tag></div>
      <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(locale === 'en' ? 'en-GB' : 'ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</time>
      <div className="row row-actions"><button className="icon-button" aria-label={t('Удалить дело {0}', [item.job_id])} onClick={() => { setDeleting(item); setDeleteError(''); }}><Trash2 size={15}/></button><button className="icon-button" aria-label={t('Открыть дело {0}', [item.job_id])} onClick={() => open(item.job_id)}><ChevronRight size={19}/></button></div>
    </div>)}</div>}
    {!request.loading && !request.error && !items.length && <div className="empty"><FolderOpen size={36}/><h2>{query || filter !== 'all' ? t('Подходящих дел нет') : t('Первое дело начинается с видео')}</h2><p>{query || filter !== 'all' ? t('Измените поиск или фильтр.') : t('Загрузите MOV, чтобы получить результат с привязкой ко времени и доказательствами.')}</p>{!query && filter === 'all' && <button className="button secondary" onClick={newAnalysis}><Plus size={17}/>{t('Добавить видео')}</button>}</div>}
    <div className="list-footnote"><ShieldCheck size={16}/>{t('Выводы системы помогают проверяющему и не являются юридическим заключением.')}</div>
    {deleting && <Modal title={t('Удалить дело?')} close={() => { if (!deleteBusy) setDeleting(undefined); }}><p>{t('Дело «')}{content(deleting.filename)}{t('» и сохранённые материалы будут удалены на сервере. Это действие нельзя отменить.')}</p>{deleteError && <ErrorNotice message={deleteError}/>}<div className="modal-actions"><button className="button secondary" disabled={deleteBusy} onClick={() => setDeleting(undefined)}>{t('Отмена')}</button><button className="button destructive" disabled={deleteBusy} onClick={remove}>{deleteBusy ? t('Удаление…') : t('Удалить дело')}</button></div></Modal>}
  </section>;
}
