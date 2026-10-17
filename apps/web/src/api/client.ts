import { validate, validateCase } from './validation';
import type { ReviewApi, CaseList, Review, ReviewInput, RuleRegistry, HealthReady } from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string, public retryAfter?: string | null) { super(message); }
}
const messages: Record<number, string> = {
  401: 'Ключ доступа не принят. Переподключитесь с правильным ключом.',
  403: 'У ключа нет прав на это действие.',
  404: 'Дело или функция не найдены на сервере.',
  409: 'Материал ещё готовится. Повторите запрос позже.',
  413: 'Файл превышает допустимый размер.',
  415: 'Сервер не поддерживает этот формат видео.',
  422: 'Сервер отклонил данные. Проверьте формат файла или поля.',
  429: 'Очередь заполнена. Повторите загрузку позже.',
  503: 'Модель или обработчик пока не готовы. Проверьте раздел «Система».',
};
export const errorText = (error: unknown) => error instanceof ApiError && error.status === 429 && error.retryAfter && /^\d+$/.test(error.retryAfter) ? `${error.message} Сервер рекомендует подождать ${error.retryAfter} сек.` : error instanceof Error ? error.message : 'Не удалось выполнить действие.';

export class HttpApi implements ReviewApi {
  readonly synthetic = false;
  constructor(private key: string) {}
  private async request(path: string, init: RequestInit = {}, signal?: AbortSignal, allowNotReady = false): Promise<Response> {
    let response: Response;
    try {
      response = await fetch(path, { ...init, redirect: 'error', cache: 'no-store', credentials: 'omit', headers: { ...init.headers, 'X-API-Key': this.key }, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(30000) });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new Error('Нет связи с сервером. Проверьте подключение и повторите запрос.');
    }
    if (!response.ok && !(allowNotReady && response.status === 503)) throw new ApiError(response.status, messages[response.status] || `Ошибка сервера (${response.status}).`, response.headers.get('Retry-After'));
    return response;
  }
  async list(signal?: AbortSignal) { return validate<CaseList>('CaseList', await (await this.request('/api/ui/cases', {}, signal)).json()); }
  async case(id: string, signal?: AbortSignal) { return validateCase(await (await this.request(`/api/ui/cases/${encodeURIComponent(id)}`, {}, signal)).json()); }
  async rules(signal?: AbortSignal) { return validate<RuleRegistry>('RuleRegistry', await (await this.request('/api/ui/rules', {}, signal)).json()); }
  async health(signal?: AbortSignal) {
    const health = validate<HealthReady>('HealthReady', await (await this.request('/health/ready', {}, signal, true)).json());
    if (health.contract_version !== '1.0.0') throw new Error('Версия API сервера несовместима с интерфейсом (ожидается 1.0.0).');
    return health;
  }
  async review(id: string, event: string, input: ReviewInput, signal?: AbortSignal) {
    return validate<Review>('Review', await (await this.request(`/api/ui/cases/${encodeURIComponent(id)}/reviews/${encodeURIComponent(event)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }, signal)).json());
  }
  async blob(id: string, kind: 'media' | 'bundle', signal?: AbortSignal) {
    const response = await this.request(`/api/ui/cases/${encodeURIComponent(id)}/${kind}`, {}, signal);
    const mime = kind === 'media' ? 'video/mp4' : 'application/zip';
    if (!response.headers.get('Content-Type')?.toLowerCase().startsWith(mime)) throw new Error('Сервер вернул материал в неожиданном формате.');
    return response.blob();
  }
  async remove(id: string, signal?: AbortSignal) { await this.request(`/api/ui/cases/${encodeURIComponent(id)}`, { method: 'DELETE' }, signal); }
  upload(file: File, progress: (percent: number | null) => void, signal?: AbortSignal): Promise<string> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const abort = () => xhr.abort();
      if (signal?.aborted) { reject(new DOMException('Aborted', 'AbortError')); return; }
      xhr.open('POST', '/api/v1/analyze');
      xhr.setRequestHeader('X-API-Key', this.key);
      xhr.timeout = 300000;
      xhr.upload.onprogress = e => progress(e.lengthComputable ? Math.round(e.loaded / e.total * 100) : null);
      xhr.onloadend = () => signal?.removeEventListener('abort', abort);
      xhr.onload = () => {
        if (xhr.status !== 202) { reject(new ApiError(xhr.status, messages[xhr.status] || `Загрузка не принята (${xhr.status}).`, xhr.getResponseHeader('Retry-After'))); return; }
        try { resolve(validate<{job_id: string}>('UploadAccepted', JSON.parse(xhr.responseText)).job_id); }
        catch (e) { reject(e); }
      };
      xhr.onerror = () => reject(new Error('Передача прервана. Проверьте список дел перед повторной загрузкой.'));
      xhr.ontimeout = () => reject(new Error('Истекло время передачи. Проверьте список дел перед повторной загрузкой.'));
      xhr.onabort = () => reject(new DOMException('Aborted', 'AbortError'));
      signal?.addEventListener('abort', abort, { once: true });
      const body = new FormData(); body.append('file', file); xhr.send(body);
    });
  }
}
