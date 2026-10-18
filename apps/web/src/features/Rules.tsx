import { useI18n } from '../i18n';
import { useState } from 'react';
import { Search, ExternalLink, BookOpen, ShieldCheck, Info } from 'lucide-react';
import type { ReviewApi, Rule } from '../api/types';
import { useRequest } from '../lib/useRequest';
import { legalUrl } from '../lib/time';
import { ErrorNotice, Loading, Modal, Tag } from '../components/ui';

export function RuleContent({ rule, format = value => value }: { rule: Rule; format?: (value: string) => string }) {
  const { t } = useI18n();
  const url = legalUrl(rule.source_url);
  const [sourceError, setSourceError] = useState('');
  return <div className="rule-content"><div className="row"><Tag tone={rule.enabled ? 'mint' : 'amber'}>{rule.enabled ? t("Активная норма") : t("Не применяется")}</Tag><span className="mono muted">{rule.rule_id}</span></div>
    <h3>{format(rule.display_name)}</h3><p>{format(rule.document_title)}</p>
    <dl className="metadata"><div><dt>{t("Пункт / статья")}</dt><dd>{format(rule.clause)}</dd></div><div><dt>{t("Редакция")}</dt><dd>{format(rule.revision)}</dd></div><div><dt>{t("Действует с")}</dt><dd>{rule.effective_date ?? t("Дата не указана")}</dd></div></dl>
    <h4>{t("Область применения")}</h4><p className="muted">{format(rule.applicability)}</p><h4>{t("Исключения")}</h4>{rule.exclusions.length ? <ul>{rule.exclusions.map((text, i) => <li key={i}>{format(text)}</li>)}</ul> : <p className="muted">{t("Не указаны в источнике сервера.")}</p>}
    {rule.source_sha256 && <details><summary>{t("Контрольная сумма источника")}</summary><code className="hash">{rule.source_sha256}</code></details>}
    {url ? <a className="button secondary full" href={url} target="_blank" rel="noreferrer" onClick={e => { if (!navigator.onLine) { e.preventDefault(); setSourceError('Нет подключения к сети. Сохранённые сведения о норме доступны в этой карточке.'); } else if (window.cashproof) { e.preventDefault(); void window.cashproof.openSource(url).catch(() => setSourceError('Не удалось открыть официальный источник.')); } }}><ExternalLink size={16}/>{t("Открыть официальный источник")}</a> : <div className="notice warning"><Info size={17}/>{t("Официальная ссылка не подтверждена. Норма не открывается автоматически.")}</div>}
    {sourceError && <ErrorNotice message={sourceError}/>}
  </div>;
}
export function RuleDrawer({ rules, close, format }: { rules: Rule[]; close: () => void; format?: (value: string) => string }) {
  const { t } = useI18n(); return <Modal title={t("Источник и основание")} close={close}><p className="muted small">{t("Снимок нормы на момент анализа. Последующие изменения библиотеки не меняют это дело.")}</p>{rules.length ? rules.map(r => <RuleContent key={r.rule_id} rule={r} format={format}/>) : <ErrorNotice message={t("Сервер не передал источник для события.")}/>}</Modal>; }

export function Rules({ api }: { api: ReviewApi }) {
  const { t } = useI18n();
  const request = useRequest(signal => api.rules(signal), [api]); const [query, setQuery] = useState(''); const [selected, setSelected] = useState<Rule>();
  const { locale } = useI18n();
  const content = (value: string) => api.synthetic ? api.demoText?.(value, locale) ?? value : value;
  const rules = request.data?.rules.filter(r => `${content(r.display_name)} ${content(r.document_title)} ${content(r.clause)}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())) ?? [];
  return <section className="page"><div className="eyebrow">{t("БАЗА ОСНОВАНИЙ")}</div><h1>{t("Библиотека норм")}</h1><p className="page-description">{t("Проверенные источники, область применения и исключения. Правило доступно анализатору только после активации.")}</p>
    <div className="section-toolbar"><label className="search"><Search size={18}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder={t("Найти документ или норму")} aria-label={t("Поиск норм")}/></label><span className="muted small">{api.synthetic ? t("Учебная библиотека") : t("Версия {0}", [request.data?.version ?? '—'])}</span></div>
    {request.loading && <Loading/>}{request.error && <ErrorNotice message={request.error} retry={request.retry}/>}
    <div className="rule-grid">{rules.map(r => <button key={r.rule_id} className="rule-card" onClick={() => setSelected(r)}><span className="rule-icon"><BookOpen size={22}/></span><Tag tone={r.enabled ? 'mint' : 'amber'}>{r.enabled ? t("Активна") : t("Отключена")}</Tag><h3>{content(r.display_name)}</h3><p>{content(r.document_title)}</p><div className="rule-card-footer"><span>{content(r.clause)}</span><span><ShieldCheck size={15}/>{content(r.revision)}</span></div></button>)}</div>
    {!request.loading && !request.error && !rules.length && <div className="empty"><BookOpen size={28}/><h3>{t("Нет подходящих норм")}</h3><p>{t("Измените запрос или дождитесь публикации источников сервером.")}</p></div>}
    {selected && <RuleDrawer format={content} rules={[selected]} close={() => setSelected(undefined)}/>}
  </section>;
}
