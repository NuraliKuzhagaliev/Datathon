import { useEffect, useState } from 'react';
import { errorText } from '../api/client';

export function useRequest<T>(load: (signal: AbortSignal) => Promise<T>, dependencies: unknown[], interval = 0) {
  const [state, set] = useState<{data?: T; error?: string; loading: boolean}>({ loading: true });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    set({ loading: true });
    async function run() {
      try { const data = await load(controller.signal); if (!controller.signal.aborted) { failures = 0; set({ data, loading: false }); } }
      catch (e) { if (!controller.signal.aborted) { failures++; set(previous => ({ ...previous, error: errorText(e), loading: false })); } }
      if (interval && !controller.signal.aborted) timer = setTimeout(run, Math.min(interval * 2 ** failures, 15000));
    }
    void run();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [...dependencies, retry]);
  return { ...state, retry: () => setRetry(v => v + 1) };
}
