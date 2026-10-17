import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Review, ReviewApi, ReviewInput, UiEvent } from '../api/types';
import { LogOut } from 'lucide-react';
import { useI18n } from '../i18n';
import { Modal } from '../components/ui';

type Draft = { input: ReviewInput; saved: Review };
const changed = (draft: Draft) => draft.input.note !== draft.saved.note || draft.input.decision !== draft.saved.decision;
const key = (job: string, event: string) => JSON.stringify([job, event]);
type DraftSession = {
  hasDrafts: boolean;
  read: (job: string, event: UiEvent) => Draft;
  edit: (job: string, event: UiEvent, input: ReviewInput) => void;
  acknowledge: (job: string, review: Review) => void;
  forget: (job: string) => void;
};
const Context = createContext<DraftSession | null>(null);

// Session memory only: navigating between events/cases keeps notes, while a
// different API session receives a new store. No case content reaches storage.
export function ReviewDraftProvider({ api, children }: { api?: ReviewApi; children: ReactNode }) {
  const store = useMemo(() => new Map<string, Draft>(), [api]);
  const [revision, update] = useState(0);
  const dirty = [...store.values()].some(changed);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty, store]);
  const value = useMemo<DraftSession>(() => {
    function read(job: string, event: UiEvent): Draft {
      const current = store.get(key(job, event.event_id));
      if (current && changed(current)) return current;
      // A polling response started before PUT must not undo its acknowledgement.
      const saved = current && Date.parse(current.saved.updated_at ?? '') > Date.parse(event.review.updated_at ?? '1970-01-01') ? current.saved : event.review;
      return { saved, input: { decision: saved.decision, note: saved.note } };
    }
    return {
      hasDrafts: [...store.values()].some(changed),
      read,
      edit(job, event, input) { store.set(key(job, event.event_id), { saved: read(job, event).saved, input }); update(n => n + 1); },
      acknowledge(job, review) { store.set(key(job, review.event_id), { saved: review, input: { decision: review.decision, note: review.note } }); update(n => n + 1); },
      forget(job) { for (const entry of store.keys()) if (JSON.parse(entry)[0] === job) store.delete(entry); update(n => n + 1); },
    };
  }, [store, revision]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useReviewDrafts() {
  const context = useContext(Context);
  if (!context) throw new Error('Review draft session is missing.');
  return { ...context, changed };
}

export function SessionExit({ leave }: { leave: () => void }) {
  const { t } = useI18n(); const { hasDrafts } = useReviewDrafts(); const [confirm, setConfirm] = useState(false);
  return <><button className="icon-button" aria-label={t('Отключиться')} onClick={() => hasDrafts ? setConfirm(true) : leave()}><LogOut size={17}/></button>
    {confirm && <Modal title={t('Выйти с несохранёнными черновиками?')} close={() => setConfirm(false)}><p>{t('Черновики хранятся только в памяти сеанса и будут удалены при выходе. Сохранённые на сервере решения останутся.')}</p><div className="modal-actions"><button className="button secondary" onClick={() => setConfirm(false)}>{t('Продолжить проверку')}</button><button className="button destructive" onClick={leave}>{t('Выйти без сохранения')}</button></div></Modal>}
  </>;
}
