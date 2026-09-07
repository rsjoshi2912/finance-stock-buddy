import { useEffect, useState } from 'react';
import { Activity, Clock3 } from 'lucide-react';
import { api } from './api';

type Snapshot = {
  market_open: boolean; schedule_known: boolean; refresh_seconds: number;
  quotes: {symbol: string; price: number; change: number; market_at: string; stale: boolean}[];
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
    return () => {active = false; clearInterval(timer);};
  }, []);
  const visible = data?.quotes.filter(q => !symbols.length || symbols.includes(q.symbol)).slice(0, 10) || [];
  return <section className="panel live-prices">
    <div className="panel-head"><div><h2><Activity size={16}/> Latest market prices</h2>
      <p>Checks every 15 seconds. Daily calls stay as originally saved.</p></div>
      <span className="badge">{!data?.schedule_known ? 'Hours unconfirmed' : data.market_open ? 'Market open' : 'Market closed'}</span>
    </div>
    {error && <p className="quote-note negative" role="status">{error}</p>}
    {visible.length ? <div className="quote-grid">{visible.map(q => <div className="quote-item" key={q.symbol}>
      <strong>{q.symbol}</strong><b>₹{q.price.toLocaleString('en-IN', {maximumFractionDigits: 2})}</b>
      <span className={q.change < 0 ? 'negative' : 'positive'}>{q.change > 0 ? '+' : ''}₹{q.change.toFixed(2)} vs previous close</span>
      <small><Clock3 size={11}/>{new Date(q.market_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit'})} IST</small>
      {q.stale && <small className="muted">Last known price · waiting for an update</small>}
    </div>)}</div> : <p className="quote-note">Waiting for the market-data connection. No sample prices are substituted here.</p>}
  </section>;
}
