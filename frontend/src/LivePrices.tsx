import { useEffect, useState } from 'react';
import { Activity, Clock3 } from 'lucide-react';
import { api } from './api';

type Snapshot = {
  market_open: boolean; schedule_known: boolean; refresh_seconds: number;
  provider?: string; notice?: string;
  quotes: {symbol: string; price: number; change: number; market_at: string; stale: boolean; provider?: string; possibly_delayed?: boolean}[];
};

export default function LivePrices({symbols = []}: {symbols?: string[]}) {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    async function load() {
      if (document.hidden) return;
      try { const result = await api<Snapshot>('quotes'); if (active) {setData(result); setError('');} }
      catch { if (active) setError('Prices could not be refreshed. Check System health.'); }
    }
    void load(); const timer = setInterval(load, 15000);
    window.addEventListener('journal:data-refreshed', load);
    return () => {active = false; clearInterval(timer); window.removeEventListener('journal:data-refreshed', load);};
  }, []);
  const visible = data?.quotes.filter(q => !symbols.length || symbols.includes(q.symbol)).slice(0, 10) || [];
  const delayed = data?.quotes.some(q => q.possibly_delayed);
  return <section className="panel live-prices">
    <div className="panel-head"><div><h2><Activity size={16}/> Market prices</h2>
      <p>{data?.provider || 'Market data'}{delayed ? ' · May be delayed' : ''} · {data?.refresh_seconds === 300 ? '5-minute' : '15-second'} checks</p></div>
      <span className="badge">{!data?.schedule_known ? 'Hours unconfirmed' : data.market_open ? 'Market open' : 'Market closed'}</span>
    </div>
    {error && <p className="quote-note negative" role="status">{error}</p>}
    {visible.length ? <div className="quote-grid">{visible.map(q => <div className="quote-item" key={q.symbol}>
      <strong>{q.symbol}</strong><b>₹{q.price.toLocaleString('en-IN', {maximumFractionDigits: 2})}</b>
      {q.provider && q.provider !== data?.provider && <small>{q.provider}</small>}
      <span className={q.change < 0 ? 'negative' : 'positive'}>{q.change > 0 ? '+' : ''}₹{q.change.toFixed(2)}</span>
      <small><Clock3 size={11}/>{new Date(q.market_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit'})} IST</small>
      {q.stale && <small className="quote-stale">Awaiting update</small>}
    </div>)}</div> : <p className="quote-note">No price snapshots available.</p>}
    {data?.notice && <details className="source-details"><summary>Source details</summary><p>{data.notice} Changes are measured from the previous close.</p></details>}
  </section>;
}
