import { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from './api';

type FetchState = {
  id: string | null; status: string; busy: boolean; message: string;
  retry_after_seconds: number; completed_at?: string | null;
  prices?: {status: string; detail: string} | null;
  news?: {status: string; detail: string} | null;
};

export default function FetchLatest() {
  const [state, setState] = useState<FetchState | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState('');
  const [statusError, setStatusError] = useState('');
  const lastFinished = useRef<string | null>(null);
  const waiting = Boolean(state?.busy || state?.retry_after_seconds);
  const load = useCallback(async () => {
    if (document.hidden) return;
    try { setState(await api<FetchState>('refresh')); setStatusError(''); }
    catch { setStatusError('Could not check the fetch status. Try refreshing the page.'); }
  }, []);
  useEffect(() => {
    void load(); const timer = setInterval(() => void load(), waiting ? 2000 : 30000);
    return () => clearInterval(timer);
  }, [load, waiting]);
  useEffect(() => {
    if (state?.id && !state.busy && state.status !== 'idle' && lastFinished.current !== state.id) {
      lastFinished.current = state.id;
      window.dispatchEvent(new Event('journal:data-refreshed'));
    }
  }, [state]);
  async function fetchLatest() {
    setRequesting(true); setError('');
    try { setState(await api<FetchState>('refresh', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not start the fetch.'); await load(); }
    finally { setRequesting(false); }
  }
  const busy = requesting || Boolean(state?.busy);
  return <section className="panel fetch-latest" aria-label="Fetch latest data">
    <div className="panel-head"><div><h2>Update prices and news</h2>
      <p>Fetch the newest data available from your sources.</p></div>
      <button className="button primary" onClick={() => void fetchLatest()} disabled={!state || busy || Boolean(state.retry_after_seconds)}>
        <RefreshCw size={16} className={busy ? 'fetch-spinner' : ''}/>{busy ? 'Fetching…' : 'Fetch latest'}
      </button>
    </div>
    <div className="fetch-result" role="status" aria-live="polite">
      {(error || statusError) && <p className="negative">{error || statusError}</p>}
      {state && <><p>{state.message}{state.completed_at && <> · {new Date(state.completed_at).toLocaleTimeString('en-IN', {timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit'})} IST</>}</p>
        {state.prices && <p className={state.prices.status === 'failed' ? 'negative' : ''}>Prices: {state.prices.detail}</p>}
        {state.news && <p className={state.news.status === 'failed' ? 'negative' : ''}>News: {state.news.detail}</p>}
        {!state.busy && state.retry_after_seconds > 0 && <small>Ready to fetch again in {state.retry_after_seconds} seconds.</small>}
      </>}
    </div>
  </section>;
}
