import * as validators from './generated/validators.js';
import type { CaseDetail } from './types';

export function validate<T>(name: string, value: unknown): T {
  const check = validators[name as keyof typeof validators];
  if (!check) throw new Error(`Unknown contract schema: ${name}`);
  if (!check(value)) throw new Error(`Ответ сервера не соответствует контракту 1.0.0 (${name}).`);
  return value as T;
}

export function validateCase(value: unknown, allowSynthetic = false): CaseDetail {
  const result = validate<CaseDetail>('CaseDetail', value);
  if (result.is_synthetic && !allowSynthetic) throw new Error('Рабочий сервер вернул синтетический пример. Анализ не подтверждён.');
  if (result.status === 'done' && (!result.model_result || result.model_result.job_id !== result.job_id)) throw new Error('Завершённое дело не содержит согласованного результата.');
  if (result.status !== 'done' && result.model_result) throw new Error('Незавершённое дело содержит окончательный результат.');
  if (result.status === 'failed' && !result.error) throw new Error('Сервер не указал причину сбоя.');
  if (result.status === 'done' && result.stage !== 'complete' || result.status === 'failed' && result.stage !== 'failed' || result.status === 'processing' && ['failed', 'complete'].includes(result.stage)) throw new Error('Этап и статус обработки не согласованы.');
  let sourceEnd = -1; let previewEnd = -1;
  for (const segment of result.time_map) {
    if (segment.source_end_sec <= segment.source_start_sec || segment.preview_end_sec <= segment.preview_start_sec || segment.source_start_sec < sourceEnd || segment.preview_start_sec < previewEnd || result.duration_sec !== null && segment.source_end_sec > result.duration_sec) throw new Error('Некорректная карта времени видеопросмотра.');
    sourceEnd = segment.source_end_sec; previewEnd = segment.preview_end_sec;
  }
  for (const segment of result.coverage) if (segment.end_sec <= segment.start_sec || result.duration_sec !== null && segment.end_sec > result.duration_sec) throw new Error('Некорректные интервалы покрытия анализа.');
  if (result.status === 'done' && result.events.length !== result.model_result!.violations.length) throw new Error('События интерфейса не согласованы с результатом API.');
  if (new Set(result.events.map(e => e.event_id)).size !== result.events.length) throw new Error('Сервер вернул повторяющиеся идентификаторы событий.');
  const indices = new Set<number>();
  for (const event of result.events) {
    const original = result.model_result?.violations[event.jury_violation_index];
    if (!original || indices.has(event.jury_violation_index) || original.timecode_sec !== event.timecode_sec || original.type !== event.type || JSON.stringify(original.evidence_frames) !== JSON.stringify(event.evidence_frames) || event.review.event_id !== event.event_id) throw new Error('Нарушена связь события с исходным результатом.');
    indices.add(event.jury_violation_index);
    if (event.context_start_sec > event.timecode_sec || event.context_end_sec < event.timecode_sec) throw new Error('Некорректный интервал контекста.');
    if (result.duration_sec !== null && (event.context_end_sec > result.duration_sec || event.evidence_frames.some(f => f.timestamp_sec > result.duration_sec!))) throw new Error('Доказательство выходит за длительность видео.');
    if (event.rule_ids.some(id => !result.rules.some(r => r.rule_id === id && (r.enabled || result.is_synthetic)))) throw new Error('Для события отсутствует активная норма в снимке дела.');
  }
  return result;
}
