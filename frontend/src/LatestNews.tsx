import { useEffect, useState } from 'react';
import { Newspaper } from 'lucide-react';
import { api } from './api';

type News = {
  sources: {source: string; status: string}[];
  articles: {id: number; source: string; title: string; url: string; published_at: string; symbols: string[]; stale: boolean}[];
};

export default function LatestNews() {
  const [data, setData] = useState<News | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const load = async () => {
      if (document.hidden) return;
      try { const result = await api<News>('news'); if (active) {setData(result); setError('');} }
      catch { if (active) setError('News could not be refreshed. Check System health.'); }
    };
    void load(); const timer = setInterval(load, 60000);
    return () => {active = false; clearInterval(timer);};
  }, []);
  return <section className="panel news-panel">
    <div className="panel-head"><div><h2><Newspaper size={16}/> Latest news</h2>
      <p>Public feeds checked every 5 minutes. Stock impact has not been assessed yet.</p></div></div>
    {error && <p className="quote-note negative" role="status">{error}</p>}
    <div className="news-sources">{data?.sources.map(s => <span key={s.source} className="badge">{s.source} · {s.status === 'ok' ? 'Recent news' : s.status === 'stale' ? 'Needs an update' : 'Unavailable'}</span>)}</div>
    {data?.articles.length ? <div className="news-list">{data.articles.slice(0, 8).map(a => <article key={a.id}>
      <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title}</a>
      <small>{a.source} · {new Date(a.published_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'})} IST{a.stale ? ' · Older article' : ''}{a.symbols.length ? ` · ${a.symbols.join(', ')}` : ''}</small>
    </article>)}</div> : <p className="quote-note">No public news has been collected yet.</p>}
  </section>;
}
