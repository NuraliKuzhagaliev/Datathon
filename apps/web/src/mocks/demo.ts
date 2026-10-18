import positive from '../../../../packages/contracts/fixtures/ui-positive.json';
import negative from '../../../../packages/contracts/fixtures/ui-negative.json';
import processing from '../../../../packages/contracts/fixtures/ui-processing.json';
import failed from '../../../../packages/contracts/fixtures/ui-failed.json';
import registry from '../../../../packages/contracts/fixtures/rules.json';
import { validateCase, validate } from '../api/validation';
import type { ReviewApi, ReviewInput, RuleRegistry } from '../api/types';
import { localizeDemo, demoText } from './localize';
import frames from './generated/frames.json';
import englishFrames from './generated/frames.en.json';

export function createDemo(): ReviewApi {
  if (!import.meta.env.DEV) throw new Error('Синтетическое демо доступно только при разработке.');
  const cases = [positive, negative, processing, failed].map((value, index) => {
    const copy = localizeDemo(structuredClone(value));
    copy.filename = ['Демо — два события.mov', 'Демо — без событий.mov', 'Демо — обработка.mov', 'Демо — ошибка чтения.mov'][index];
    for (const [eventIndex, event] of copy.events.entries()) {
      for (const [frameIndex, frame] of event.evidence_frames.entries()) frame.image_base64 = frames[eventIndex][frameIndex];
      if (copy.model_result) copy.model_result.violations[event.jury_violation_index].evidence_frames = structuredClone(event.evidence_frames);
    }
    return validateCase(copy, true);
  });
  return {
    synthetic: true,
    demoText,
    demoImage(value, locale) {
      if (locale === 'en') for (const [i, group] of frames.entries()) {
        const j = group.indexOf(value); if (j >= 0) return englishFrames[i][j];
      }
      return value;
    },
    async list() { return { items: cases.map(c => ({ job_id: c.job_id, filename: c.filename, created_at: c.created_at, status: c.status, verdict: c.model_result?.verdict ?? null })) }; },
    async case(id) { const c = cases.find(c => c.job_id === id); if (!c) throw new Error('Пример не найден'); return structuredClone(c); },
    async rules() { return validate<RuleRegistry>('RuleRegistry', localizeDemo(registry)); },
    async health() { return { ready: false, mode: 'server', contract_version: '1.0.0' }; },
    async upload() { throw new Error('Демо не принимает видео. Подключите настоящий сервер.'); },
    async review(id: string, eventId: string, input: ReviewInput) { const event = cases.find(c => c.job_id === id)?.events.find(e => e.event_id === eventId); if (!event) throw new Error('Событие не найдено'); event.review = { ...input, event_id: eventId, updated_at: new Date().toISOString() }; return structuredClone(event.review); },
    async blob() { throw new Error('Демо не содержит видео или настоящего ZIP. Экспорт доступен после подключения сервера анализа.'); },
    async remove(id) { const index = cases.findIndex(c => c.job_id === id); if (index >= 0) cases.splice(index, 1); },
  };
}
