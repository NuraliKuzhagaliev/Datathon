import { useI18n } from '../i18n';
import { useEffect, useRef, type ReactNode } from 'react';
import { AlertCircle, X, ScanLine, LoaderCircle } from 'lucide-react';

export function Brand() {
  const { t } = useI18n(); return <div className="brand"><span className="brand-mark"><ScanLine size={23}/></span><span>Cash<span className="brand-light">Proof</span><small>{t("ПРОВЕРКА ОПЕРАЦИЙ")}</small></span></div>; }
export function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  const { t } = useI18n(); return <div className="notice danger" role="alert"><AlertCircle size={18}/><span>{t(message)}</span>{retry && <button className="text-button" onClick={retry}>{t("Повторить")}</button>}</div>; }
export function Loading({ text = 'Загрузка…' }: { text?: string }) {
  const { t } = useI18n(); return <div className="loading" role="status"><LoaderCircle className="spinner" size={20}/>{t(text)}</div>; }
export function Modal({ title, children, close, wide = false }: { title: string; children: ReactNode; close: () => void; wide?: boolean }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const restoreFocus = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => { dialog.close(); queueMicrotask(() => { if (!dialog.isConnected && restoreFocus.current?.isConnected) restoreFocus.current.focus(); }); }; }, []);
  return <dialog ref={ref} className={wide ? 'modal wide' : 'modal'} onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === e.currentTarget) close(); }}>
    <div className="modal-inner"><header className="modal-header"><h2>{title}</h2><button className="icon-button" onClick={close} aria-label={t("Закрыть")}><X size={20}/></button></header>{children}</div>
  </dialog>;
}
export function Tag({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`tag ${tone}`}>{children}</span>; }
