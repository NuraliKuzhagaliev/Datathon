// Presentation copies only. Shared fixtures and production responses stay untouched.
const labels: Record<string, string> = {
  'Synthetic event A': 'Учебное событие 1',
  'Synthetic event B': 'Учебное событие 2',
  'Synthetic geometric scene for UI testing.': 'Условная геометрическая сцена для знакомства с интерфейсом. Это не банковская видеозапись.',
  'No inference or legal conclusion was performed.': 'Анализ моделью не выполнялся. Пример показывает, где появятся объяснение и основание для проверки.',
  'Synthetic fixture only': 'Только синтетический пример; выводов о реальных действиях нет.',
  'Synthetic visibility limit': 'Условный участок ограниченной видимости в демопримере.',
  'Synthetic failure fixture.': 'Учебный пример ошибки чтения видео.',
  'Synthetic integration fixture. This is not a finding about a person or a legal violation.': 'Синтетический пример для знакомства с интерфейсом. Это не вывод о человеке или нарушении закона.',
  'Second synthetic event to exercise navigation and multi-event responses.': 'Второе учебное событие для проверки навигации между несколькими моментами.',
  'Synthetic fixture rule': 'Учебное основание',
  'Integration fixture only': 'Синтетический пример карточки нормы. Юридической силы не имеет.',
  'Not applicable': 'Не применимо к реальным операциям',
  'UI development only': 'Только демонстрация интерфейса.',
  'Never use in production inference': 'Не используется для анализа реальных видео.',
  'synthetic': 'учебная редакция',
};

export function localizeDemo<T>(value: T): T {
  if (typeof value === 'string') return (labels[value] ?? value) as T;
  if (Array.isArray(value)) return value.map(localizeDemo) as T;
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, localizeDemo(item)])) as T;
  return value;
}

const englishLabels: Record<string, string> = Object.fromEntries(Object.entries(labels).map(([en, ru]) => [ru, en]));
Object.assign(englishLabels, {
  'Учебное событие 1': 'Demo event 1', 'Учебное событие 2': 'Demo event 2',
  'Учебное основание': 'Demo rule source', 'учебная редакция': 'demo revision',
  'Демо — два события.mov': 'Demo — two events.mov', 'Демо — без событий.mov': 'Demo — no events.mov',
  'Демо — обработка.mov': 'Demo — processing.mov', 'Демо — ошибка чтения.mov': 'Demo — decoding error.mov',
});
export const demoText = (value: string, locale: 'ru' | 'en') => locale === 'en' ? englishLabels[value] ?? value : value;
