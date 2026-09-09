import { useEffect, useRef, useState } from 'react';
import { Activity, Clock3, RefreshCw, Send } from 'lucide-react';
import { api } from './api';
import TelegramPreview from './TelegramPreview';

type Option = {action:string;reason:string;valid_until?:string|null;entry?:number;stop?:number;target?:number;planned_loss?:number;premium_at_risk?:number;target_net?:number;lot?:number;contract?:{name:string;expiry:string;quote_at:string}|null};
type IndexRead = {id?:number;symbol:string;name:string;direction:string;reason:string;assessed_at:string|null;candle_at:string|null;valid_until?:string|null;price:number|null;opening_high?:number|null;opening_low?:number|null;trend?:string|null;invalidation?:number|null;option:Option;expired?:boolean};
type Snapshot = {indices:IndexRead[];can_fetch:boolean;option_provider:string;server_time:string;notice:string;limits:{capital:number|null;risk:number|null};refresh:{busy:boolean;status:string;message:string;retry_after_seconds:number};history:{id:number;symbol:string;at:string;direction:string;option_action:string;reason:string}[]};
const when = (value:string|null|undefined) => value ? new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit'})+' IST' : 'Not checked yet';
const amount = (value:number|null|undefined) => value == null ? '—' : value.toLocaleString('en-IN',{maximumFractionDigits:2});
const directionLabel = (value:string) => value==='UP'?'Up bias':value==='DOWN'?'Down bias':'Skip';
const optionLabel = (value:string) => value==='BUY_CALL'?'Buy call':value==='BUY_PUT'?'Buy put':'Skip option';

export default function IndexSignals() {
  const [data,setData]=useState<Snapshot|null>(null), [error,setError]=useState(''), [sending,setSending]=useState(false);
  const [preview,setPreview]=useState<{text:string;html:string}|null>(null), [previewBusy,setPreviewBusy]=useState(false);
  const [now,setNow]=useState(Date.now()), [offset,setOffset]=useState(0);
  const mounted=useRef(true);
  async function load() {
    try { const value=await api<Snapshot>('indices'); if(mounted.current){setData(value);setOffset(Date.parse(value.server_time)-Date.now());setError('');} }
    catch(e) {if(mounted.current)setError(e instanceof Error?e.message:'Could not check the index signals.');}
  }
  useEffect(()=>{mounted.current=true;void load();return()=>{mounted.current=false}},[]);
  useEffect(()=>{const timer=setInterval(()=>{if(!document.hidden)void load()},data?.refresh.busy?2000:15000);return()=>clearInterval(timer)},[data?.refresh.busy]);
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer)},[]);
  async function refresh() {
    setSending(true);setError('');setPreview(null);
    try {await api('indices/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await load();}
    catch(e){setError(e instanceof Error?e.message:'Could not start the index check.');}
    finally{if(mounted.current)setSending(false);}
  }
  async function showPreview() {
    setPreviewBusy(true);
    try{setPreview(await api<{text:string;html:string}>('indices/brief'));}
    catch(e){setError(e instanceof Error?e.message:'Could not load the note.');}
    finally{setPreviewBusy(false);}
  }
  const busy=sending||data?.refresh.busy;
  return <section className="index-signals" aria-label="Index paper signals">
    <div className="index-signal-heading"><div><h2><Activity size={18}/> Index signals</h2><p>Yahoo Finance · 5-minute candles</p></div>
      <button className="button primary" onClick={()=>void refresh()} disabled={!data?.can_fetch||busy||!!data?.refresh.retry_after_seconds}><RefreshCw size={15}/>{busy?'Checking indices…':'Refresh index signals'}</button></div>
    {error&&<p className="index-fetch-message negative" role="alert">{error} Actions paused.</p>}
    {data?.refresh.status!=='idle'&&data?.refresh.message&&<p className="index-fetch-message" role="status">{data.refresh.message}{!!data.refresh.retry_after_seconds&&` Next manual check in about ${data.refresh.retry_after_seconds}s.`}</p>}
    {!data ? <p className="quote-note">Loading saved index checks…</p> : <>
      {data.option_provider==='none'&&<p className="option-feed-status">Option feed not connected · option entries unavailable</p>}
      <div className="two-columns">{data.indices.map(row=>{
        const expired=!!row.valid_until&&now+offset>=Date.parse(row.valid_until);
        const direction=error||expired?'SKIP':row.direction;
        const optionExpired=!!row.option.valid_until&&now+offset>=Date.parse(row.option.valid_until);
        const optionAction=direction==='SKIP'||optionExpired||error?'SKIP':row.option.action;
        return <article className="panel index-signal-card" key={row.symbol}>
          <div className="index-card-title"><div><h3>{row.name}</h3><span>{row.price==null?'No price yet':`${amount(row.price)} points`}</span></div><strong className={`badge ${direction==='UP'?'green':direction==='DOWN'?'red':'neutral'}`}>{directionLabel(direction)}</strong></div>
          <p className="index-signal-reason">{error?'Connection unavailable. Refresh before using a saved read.':expired?'This setup has expired. Fetch a new check.':row.reason}</p>
          <div className="index-levels"><div><span>Opening high</span><b>{amount(row.opening_high)}</b></div><div><span>Opening low</span><b>{amount(row.opening_low)}</b></div><div><span>Trend</span><b>{row.trend||'Not ready'}</b></div></div>
          {direction!=='SKIP'&&<p className="index-invalidation">Invalidation {direction==='UP'?'below':'above'} {amount(row.invalidation)} points · 15-minute horizon</p>}
          <p className="index-stamp"><Clock3 size={12}/> Candle {when(row.candle_at)}</p>
          <div className="index-option-result"><strong>{optionLabel(optionAction)}</strong>{(data.option_provider!=='none'||optionExpired||row.option.action!=='SKIP')&&<p>{optionExpired?'The option quote has expired. Fetch a new check.':direction==='SKIP'&&row.option.action!=='SKIP'?'The index setup is no longer current.':row.option.reason}</p>}
            {row.option.contract&&<p><b>{row.option.contract.name}</b><br/>Quote {when(row.option.contract.quote_at)}</p>}
            {row.option.entry!=null&&<dl><div><dt>Entry / stop / target</dt><dd>₹{amount(row.option.entry)} / ₹{amount(row.option.stop)} / ₹{amount(row.option.target)}</dd></div><div><dt>One lot · planned loss</dt><dd>{row.option.lot} units · ₹{amount(row.option.planned_loss)}</dd></div><div><dt>Maximum premium exposure + costs</dt><dd>₹{amount(row.option.premium_at_risk)}</dd></div></dl>}
          </div>
        </article>;
      })}</div>
      <details className="panel section-disclosure"><summary>Signal method and sources</summary><div className="details-body">
        <p>Opening-range breakout and immediate retest, filtered by EMA20/50. Entry checks run 09:40–14:45 IST using 150 consecutive completed candles. News and scheduled events are not inputs.</p>
        <p>Unvalidated research; Yahoo candles may be delayed. Saved checks are assessments, not option fills or scored trades.</p>
        <p>Signal capital ₹{amount(data.limits.capital)} · planned-loss limit ₹{amount(data.limits.risk)}. Quotes must pass identity, age, spread, depth and funding checks. Calculator inputs are separate.</p>
        {data.indices.map(row=><p key={row.symbol}>{row.name} checked {when(row.assessed_at)}</p>)}
      </div></details>
      <details className="panel section-disclosure index-signal-history"><summary>Recent saved checks · {data.history.length}</summary>{data.history.length?<div className="table-scroll"><table><thead><tr><th>Time (IST)</th><th>Index</th><th>Direction</th><th>Option</th><th>Reason</th></tr></thead><tbody>{data.history.map(row=><tr key={row.id}><td>{when(row.at)}</td><td>{row.symbol}</td><td>{directionLabel(row.direction)}</td><td>{optionLabel(row.option_action)}</td><td>{row.reason}</td></tr>)}</tbody></table></div>:<p>No saved checks yet.</p>}</details>
      <div className="index-preview-action"><button className="button secondary small" onClick={()=>void showPreview()} disabled={previewBusy}>{previewBusy?<RefreshCw size={14}/>:<Send size={14}/>}Preview index Telegram note</button></div>
      {preview&&<div className="index-note-preview"><button className="text-button" onClick={()=>setPreview(null)}>Close preview</button><TelegramPreview html={preview.html} text={preview.text}/><p className="quote-note">Snapshot preview · not sent</p></div>}
    </>}
  </section>;
}
