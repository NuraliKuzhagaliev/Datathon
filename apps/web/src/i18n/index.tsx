import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import english from './en.json';

export type Locale = 'ru' | 'en';
export const LANGUAGE_KEY = 'cashproof.language';
const messages: Record<string, string> = english;

// Only interface messages are translated. Server evidence, legal sources,
// filenames and operator notes are deliberately outside this dictionary.
export function translate(message: string, locale: Locale, values: readonly (string | number)[] = []): string {
  let result = locale === 'en' ? messages[message] ?? message : message;
  if (locale === 'en' && result === message) {
    const retry = message.match(/^(.*) Сервер рекомендует подождать (\d+) сек\.$/);
    if (retry) result = `${translate(retry[1], locale)} The server recommends waiting ${retry[2]} seconds.`;
    const status = message.match(/^(Ошибка сервера|Загрузка не принята) \((\d+)\)\.$/);
    if (status) result = `${status[1] === 'Ошибка сервера' ? 'Server error' : 'Upload rejected'} (${status[2]}).`;
    const schema = message.match(/^Ответ сервера не соответствует контракту 1\.0\.0 \(([^)]+)\)\.$/);
    if (schema) result = `The server response does not match contract 1.0.0 (${schema[1]}).`;
  }
  return result.replace(/\{(\d+)\}/g, (match, index) => values[Number(index)] === undefined ? match : String(values[Number(index)]));
}

function readLocale(): Locale {
  try { return localStorage.getItem(LANGUAGE_KEY) === 'en' ? 'en' : 'ru'; } catch { return 'ru'; }
}
type I18n = { locale: Locale; setLocale: (value: Locale) => void; t: (message: string, values?: readonly (string | number)[]) => string };
const Context = createContext<I18n>({ locale: 'ru', setLocale: () => {}, t: message => message });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, updateLocale] = useState<Locale>(readLocale);
  const value = useMemo<I18n>(() => ({ locale, t: (message, values) => translate(message, locale, values), setLocale(next) {
    updateLocale(next);
    // Store only the language preference; keys and case data remain in memory.
    try { localStorage.setItem(LANGUAGE_KEY, next); } catch { /* Private/storage-disabled sessions still work. */ }
  } }), [locale]);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = `CashProof — ${translate('Проверка операций', locale)}`;
    document.querySelector('meta[name="description"]')?.setAttribute('content', translate('CashProof — рабочее место проверки кассовых операций по видео.', locale));
  }, [locale]);
  useEffect(() => {
    const sync = (event: StorageEvent) => { if (event.key === LANGUAGE_KEY || event.key === null) updateLocale(readLocale()); };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export const useI18n = () => useContext(Context);

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();
  return <div className="language-switch" role="group" aria-label={t('Язык интерфейса')}>
    <button type="button" lang="ru" aria-label="Русский" aria-pressed={locale === 'ru'} onClick={() => setLocale('ru')}>RU</button>
    <button type="button" lang="en" aria-label="English" aria-pressed={locale === 'en'} onClick={() => setLocale('en')}>EN</button>
  </div>;
}
