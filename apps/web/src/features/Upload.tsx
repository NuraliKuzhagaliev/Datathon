import { useI18n } from '../i18n';
import { useEffect, useRef, useState } from 'react';
import { UploadCloud, FileVideo, ArrowRight, ShieldCheck } from 'lucide-react';
import { ErrorNotice, Modal } from '../components/ui';
import { errorText } from '../api/client';
import type { ReviewApi } from '../api/types';

export function Upload({ api, close, accepted }: { api: ReviewApi; close: () => void; accepted: (id: string) => void }) {
  const { t } = useI18n();
  const [file, setFile] = useState<File>(); const [error, setError] = useState('');
  const [busy, setBusy] = useState(false); const [progress, setProgress] = useState<number | null>(null);
  const [drag, setDrag] = useState(false); const input = useRef<HTMLInputElement>(null); const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  function choose(candidate?: File) {
    if (!candidate || busy) return;
    setError(''); setFile(undefined);
    if (!/\.mov$/i.test(candidate.name)) { setError('Выберите видео в формате MOV.'); return; }
    if (!candidate.size || candidate.size > 128 * 1024 * 1024) { setError('Файл должен быть непустым и не больше 128 МБ.'); return; }
    setFile(candidate);
  }
  async function send() {
    if (!file || busy) return;
    const controller = new AbortController(); active.current = controller; setBusy(true); setError('');
    try { const id = await api.upload(file, setProgress, controller.signal); if (!controller.signal.aborted) accepted(id); }
    catch (e) { if (!controller.signal.aborted) setError(errorText(e)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <Modal title={t("Новый анализ")} close={close}>
    <p className="muted">{t("Добавьте видео кассовой операции. Результат и доказательства появятся в отдельном деле.")}</p>
    {api.synthetic ? <div className="notice warning">{t("В синтетическом демо загрузка отключена. Для анализа подключите сервер команды.")}</div> : <>
      <button className={`dropzone ${drag ? 'drag' : ''}`} disabled={busy} onClick={() => input.current?.click()} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); choose(e.dataTransfer.files[0]); }}>
        <span className="upload-emblem"><UploadCloud size={30}/></span><strong>{file ? file.name : t("Перетащите видео сюда")}</strong><span>{file ? t("{0} МБ · MOV", [(file.size / 1024 / 1024).toFixed(1)]) : t("или нажмите, чтобы выбрать файл")}</span><small>{t("MOV · до 128 МБ")}</small>
      </button><input ref={input} type="file" accept=".mov,video/quicktime" hidden onChange={e => choose(e.target.files?.[0])}/>
      {busy && <div className="upload-progress" role="status"><div className="row"><span>{t("Передача файла")}</span><span>{progress === null ? '…' : `${progress}%`}</span></div><progress max="100" {...(progress === null ? {} : { value: progress })}/><small>{t("После передачи начнётся обработка. Закрытие окна прервёт передачу; уже принятое дело останется в списке.")}</small></div>}
      {error && <ErrorNotice message={error}/>}
      <button className="button primary full" disabled={!file || busy} onClick={send}><FileVideo size={18}/>{busy ? t("Файл передаётся…") : t("Начать анализ")}{!busy && <ArrowRight size={18}/>}</button>
    </>}
    <p className="privacy-note"><ShieldCheck size={17}/>{t("Анализ видеоряда без аудио и распознавания личности. Обработка выполняется на выбранном сервере команды.")}</p>
  </Modal>;
}
