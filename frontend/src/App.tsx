import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3, BookOpen, CalendarDays, Check, CheckCheck, ChevronLeft, ChevronRight, CircleHelp, Clock3, Download, ExternalLink, FlaskConical, History, Info, LayoutDashboard, LockKeyhole, Menu, Search, Send, Sparkles, Target, TrendingUp, X } from 'lucide-react';
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts';
import type { Call, Dashboard, Health, Point, Stock, Summary, Track } from './types';
import { api, downloadCalls } from './api';
import EventNotes from './EventNotes';
import FetchLatest from './FetchLatest';
import IndexLab from './IndexLab';
import LatestNews from './LatestNews';
import LivePrices from './LivePrices';
import TelegramPreview from './TelegramPreview';

const money = (n: number | null | undefined, sign = true) => n == null ? '—' : `${n < 0 ? '−' : sign && n > 0 ? '+' : ''}₹${Math.abs(n).toLocaleString('en-IN', {maximumFractionDigits: 2, minimumFractionDigits: 2})}`;
const price = (n: number) => `₹${n.toLocaleString('en-IN', {maximumFractionDigits: 2})}`;
const shortDate = (s: string) => new Date(`${s}T12:00:00`).toLocaleDateString('en-IN', {day: 'numeric', month: 'short'});
const fullDate = (s: string) => new Date(`${s}T12:00:00`).toLocaleDateString('en-IN', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'});
const tone = (n: number | null | undefined) => n == null ? 'muted' : n < 0 ? 'negative' : n > 0 ? 'positive' : 'muted';
const level = (call: Call, value: number) => call.kind === 'index' ? `${value.toLocaleString('en-IN', {maximumFractionDigits: 2})} pts` : price(value);
const nav = [
  {id: 'today', label: 'Today', icon: LayoutDashboard},
  {id: 'record', label: 'Track record', icon: BarChart3},
  {id: 'history', label: 'Calls by day', icon: CalendarDays},
  {id: 'stock', label: 'Look up a stock', icon: Search},
  {id: 'indices', label: 'Index lab', icon: TrendingUp},
  {id: 'health', label: 'System health', icon: Activity},
] as const;
type Page = typeof nav[number]['id'];

function useApi<T>(path: string, refreshMs = 0) {
  const [data, setData] = useState<T | null>(null), [error, setError] = useState('');
  const [loading, setLoading] = useState(true), [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    const load = () => api<T>(path).then(value => {
      if (active) {setData(value); setError('');}
    }).catch(e => {if (active) setError(e.message);}).finally(() => {if (active) setLoading(false);});
    void load();
    const timer = refreshMs ? setInterval(() => {if (!document.hidden) void load();}, refreshMs) : undefined;
    return () => {active = false; if (timer) clearInterval(timer);};
  }, [path, revision, refreshMs]);
  return {data, error, loading, reload: () => setRevision(x => x + 1)};
}

function Badge({children, tint = 'neutral'}: {children: ReactNode; tint?: string}) {
  return <span className={`badge ${tint}`}>{children}</span>;
}
function Panel({title, subtitle, action, children, className = ''}: {title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string}) {
  return <section className={`panel ${className}`}>
    {title && <div className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>}
    {children}
  </section>;
}
function Empty({title = 'No records yet', children}: {title?: string; children?: ReactNode}) {
  return <div className="empty"><BookOpen size={26}/><h3>{title}</h3>{children && <p>{children}</p>}</div>;
}
function Failure({message, retry}: {message: string; retry: () => void}) {
  return <div className="error-box" role="alert"><Info size={20}/><div><strong>Couldn’t load this page</strong><p>{message}</p><button className="button secondary small" onClick={retry}>Try again</button></div></div>;
}
function Loading() {
  return <div className="skeleton-grid" aria-label="Loading journal" role="status"><div/><div/><div/><div/><div className="wide"/></div>;
}
function Result({call}: {call: Call}) {
  return <Badge tint={call.result === 'Right' ? 'green' : call.result === 'Wrong' ? 'red' : 'neutral'}>
    {call.result === 'Right' ? <Check size={12}/> : call.result === 'Wrong' ? <X size={12}/> : <Clock3 size={12}/>} {call.result}
  </Badge>;
}
function Avatar({symbol, index = 0}: {symbol: string; index?: number}) {
  return <span className={`stock-avatar hue-${index % 5}`}>{symbol.slice(0, 2)}</span>;
}
function Metrics({summary, last, showTotal = false, resultLabel = 'Last session'}: {summary: Summary; last?: Summary; showTotal?: boolean; resultLabel?: string}) {
  const s = last || summary, hasResults = s.days > 0;
  const values = [
    {title: showTotal ? 'Total result' : resultLabel, value: money(hasResults ? s.pnl : null), note: s.pending ? `${s.pending} ${s.pending === 1 ? 'call' : 'calls'} pending` : hasResults ? 'After trading costs' : 'No resolved session', icon: TrendingUp, tint: tone(hasResults ? s.pnl : null)},
    {title: 'Simply buying', value: money(hasResults ? s.baseline_pnl : null), note: 'Same stocks and allocation', icon: ArrowUpRight, tint: tone(hasResults ? s.baseline_pnl : null)},
    {title: 'Calls right', value: s.total ? `${s.right} / ${s.total}` : '—', note: s.total ? `${s.accuracy}% · simply buying ${s.baseline_accuracy}%` : 'Awaiting results', icon: Target, tint: ''},
    {title: 'Recorded sessions', value: `${summary.days}`, note: `${summary.winning_days} positive · ${summary.losing_days} negative`, icon: CalendarDays, tint: ''},
  ];
  return <div className="metrics">{values.map(v => <div className="metric" key={v.title}>
    <div className="metric-label">{v.title}<v.icon size={16}/></div>
    <div className="metric-value-row"><strong className={v.tint}>{v.value}</strong></div><p>{v.note}</p>
  </div>)}</div>;
}
function Legend() {
  return <div className="legend"><span><i className="blue-dot"/>Our calls</span><span><i className="gray-dot"/>Simply buying</span></div>;
}
function MoneyChart({points}: {points: Point[]}) {
  if (!points.length) return <Empty title="No completed results yet"/>;
  return <div className="chart" aria-label="Cumulative result compared with simply buying">
    <ResponsiveContainer width="100%" height={240}><ComposedChart data={points} margin={{top: 12, right: 12, bottom: 0, left: -10}}>
      <defs><linearGradient id="blueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#427bec" stopOpacity={.13}/><stop offset="100%" stopColor="#427bec" stopOpacity={0}/></linearGradient></defs>
      <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9edf3"/>
      <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={50} axisLine={false} tickLine={false} tick={{fontSize: 11, fill: '#8b95a6'}} dy={9}/>
      <YAxis tickFormatter={n => `₹${n}`} axisLine={false} tickLine={false} tick={{fontSize: 11, fill: '#8b95a6'}}/>
      <Tooltip labelFormatter={label => shortDate(String(label))} formatter={(value, name) => [money(Number(value)), name === 'model' ? 'Our calls' : 'Simply buying']}/>
      <ReferenceLine y={0} stroke="#b7c0ce" strokeDasharray="4 4"/>
      <Area isAnimationActive={false} dataKey="model" type="monotone" fill="url(#blueFill)" stroke="#3972e2" strokeWidth={2.3}/>
      <Line isAnimationActive={false} dataKey="baseline" type="monotone" stroke="#9faabc" strokeWidth={2} strokeDasharray="5 4" dot={false}/>
    </ComposedChart></ResponsiveContainer>
  </div>;
}

function CallList({calls, direction, open}: {calls: Call[]; direction: 'UP' | 'DOWN'; open: (call: Call) => void}) {
  const selected = calls.filter(x => x.direction === direction).sort((a, b) => (a.rank || 0) - (b.rank || 0));
  if (!selected.length) return null;
  return <Panel className="call-panel">
    <div className="call-heading"><div><span className={`direction-icon ${direction === 'UP' ? 'green' : 'red'}`}>{direction === 'UP' ? <ArrowUpRight size={19}/> : <ArrowDownRight size={19}/>}</span><h2>{direction === 'UP' ? 'Buy calls' : 'Sell calls'} <span>{selected.length}</span></h2></div><span className="muted small-text">Rule score</span></div>
    {selected.map((call, index) => <button className="call-row" key={call.id} onClick={() => open(call)}>
      <Avatar symbol={call.symbol} index={index}/>
      <span className="call-name"><strong>{call.symbol}{call.kind === 'index' && <em>Index</em>}</strong><span>{call.name}</span></span>
      <span className="call-price-range"><strong>{level(call, call.expected_low)} – {level(call, call.expected_high)}</strong><small>Alert {level(call, call.stop)}</small></span>
      <span className="call-confidence"><strong>{call.confidence}%</strong></span><ChevronRight size={15} className="muted"/>
    </button>)}
  </Panel>;
}
function CallsTable({calls, open}: {calls: Call[]; open: (call: Call) => void}) {
  if (!calls.length) return <Empty title="No calls match this view"/>;
  return <div className="table-scroll"><table><thead><tr><th>Stock</th><th>Call</th><th>Rule score</th><th>Result</th><th className="align-right">Our call</th><th className="align-right">Simply buying</th><th/></tr></thead>
    <tbody>{calls.map(call => <tr key={call.id}>
      <td><button className="table-stock" onClick={() => open(call)}><strong>{call.symbol}</strong><span>{call.name}</span></button></td>
      <td><span className={call.direction === 'UP' ? 'positive' : 'negative'}>{call.direction === 'UP' ? 'Buy' : 'Sell'}</span></td>
      <td>{call.confidence}%</td><td><Result call={call}/></td>
      <td className={`align-right tabular ${tone(call.pnl)}`}>{call.kind === 'index' ? <span className="muted">Direction only</span> : money(call.pnl)}</td>
      <td className="align-right tabular muted">{call.kind === 'index' ? '—' : money(call.baseline_pnl)}</td>
      <td><button className="icon-button" aria-label={`View ${call.symbol} call`} onClick={() => open(call)}><ChevronRight size={16}/></button></td>
    </tr>)}</tbody></table></div>;
}
function DailyCallNotice({data, navigate}: {data: Dashboard; navigate: (page: Page) => void}) {
  if (data.calls.length) return null;
  const status = data.daily_status;
  return <Panel className="daily-call-notice" title={status?.status === 'waiting' ? 'Morning checks pending' : 'No stock calls today'}>
    <p>{status?.reason || 'No morning calls have been saved yet.'}</p>
    {data.mode === 'live' && status && <p className="muted small-text">{status.telegram === 'sent' ? 'Telegram: delivered' : status.telegram === 'unconfirmed' ? 'Telegram: delivery unconfirmed · check before retrying' : 'Telegram: not sent'}</p>}
    {data.dates.length > 0 && <button className="text-button" onClick={() => navigate('history')}>See previous calls <ArrowRight size={14}/></button>}
  </Panel>;
}
function Today({data, open, navigate}: {data: Dashboard; open: (call: Call) => void; navigate: (page: Page) => void}) {
  const [wrong, setWrong] = useState(false);
  const buys = data.calls.filter(call => call.direction === 'UP').length;
  const sells = data.calls.length - buys;
  const allocation = data.calls.reduce((sum, call) => sum + (call.kind === 'stock' ? call.allocation : 0), 0);
  const hasTodayResults = data.calls.some(call => call.result !== 'Pending');
  return <>
    <DailyCallNotice data={data} navigate={navigate}/>
    {data.calls.length > 0 && <section aria-label="Daily calls">
      <div className="section-title"><div><h2>{data.calls.length} {data.calls.length === 1 ? 'call' : 'calls'} · {buys} Buy / {sells} Sell</h2><p>Open → close · {money(allocation, false)} stock allocation</p></div><Badge><Clock3 size={13}/> Cutoff 07:00 IST</Badge></div>
      <div className={`two-columns calls-grid ${!buys || !sells ? 'single-direction' : ''}`}><CallList calls={data.calls} direction="UP" open={open}/><CallList calls={data.calls} direction="DOWN" open={open}/></div>
    </section>}
    <Metrics summary={data.summary} last={hasTodayResults && data.today_summary ? data.today_summary : data.yesterday_summary} resultLabel={hasTodayResults && data.today_summary ? 'Today’s result' : 'Last session'}/>
    {hasTodayResults && <details className="panel section-disclosure"><summary>Today’s results</summary><CallsTable calls={data.calls} open={open}/></details>}
    {data.yesterday.length > 0 && <details className="panel section-disclosure previous-results">
      <summary>Previous results · {shortDate(data.previous_date!)}<span>{money(data.yesterday_summary.days ? data.yesterday_summary.pnl : null)}</span></summary>
      <div className="details-toolbar"><label className="switch-label"><input type="checkbox" checked={wrong} onChange={e => setWrong(e.target.checked)}/><span className="switch"/>Only wrong calls</label><button className="text-button" onClick={() => navigate('record')}>Track record <ArrowRight size={14}/></button></div>
      <CallsTable calls={data.yesterday.filter(call => !wrong || call.result === 'Wrong')} open={open}/>
    </details>}
    {data.mode === 'live' && <section className="market-overview" aria-label="Market data">
      <FetchLatest/><LivePrices symbols={data.calls.map(call => call.symbol)}/><LatestNews/>
    </section>}
  </>;
}

function RecordPage() {
  const {data, error, loading, reload} = useApi<Track>('track-record');
  if (error) return <Failure message={error} retry={reload}/>;
  if (loading || !data) return <Loading/>;
  const summary = data.summary;
  return <><Metrics summary={summary} showTotal/>
    <Panel title="Cumulative result" subtitle="After trading costs" action={<Legend/>}>
      <MoneyChart points={summary.equity}/>
      {summary.days > 0 && <div className="performance-strip"><span>Difference <strong className={tone(summary.difference)}>{money(summary.difference)}</strong></span><span>Best day <strong>{money(summary.best_day)}</strong></span><span>Worst day <strong>{money(summary.worst_day)}</strong></span><span>Max drawdown <strong>{money(-summary.max_drawdown)}</strong></span></div>}
    </Panel>
    <Panel title="Monthly results">
      {data.months.length ? <div className="table-scroll"><table><thead><tr><th>Month</th><th>Calls right</th><th>Positive / negative days</th><th className="align-right">Our calls</th><th className="align-right">Simply buying</th><th className="align-right">Difference</th></tr></thead><tbody>{data.months.map(month => <tr key={month.month}>
        <td>{new Date(`${month.month}-01T12:00:00`).toLocaleDateString('en-IN', {month: 'long', year: 'numeric'})}</td><td>{month.right} / {month.total}</td><td>{month.winning_days} / {month.losing_days}</td><td className={`align-right ${tone(month.pnl)}`}>{money(month.pnl)}</td><td className="align-right muted">{money(month.baseline_pnl)}</td><td className={`align-right ${tone(month.difference)}`}>{money(month.difference)}</td>
      </tr>)}</tbody></table></div> : <Empty title="No completed sessions"/>}
    </Panel>
    <details className="panel section-disclosure"><summary>Accuracy and breakdowns</summary><div className="details-body">
      <div className="two-columns">
        <Panel title="Direction accuracy" subtitle="Rolling 30 recorded sessions" action={<Legend/>}>
          {data.rolling.length ? <ResponsiveContainer width="100%" height={240}><ComposedChart data={data.rolling} margin={{right: 20, left: -15, top: 20}}>
            <CartesianGrid vertical={false} strokeDasharray="3 5" stroke="#e9edf3"/><XAxis dataKey="date" tickFormatter={shortDate} minTickGap={55} tick={{fontSize: 11}} axisLine={false} tickLine={false}/><YAxis domain={[0, 100]} tickFormatter={n => `${n}%`} tick={{fontSize: 11}} axisLine={false} tickLine={false}/><Tooltip formatter={(v, n) => [`${v}%`, n === 'model' ? 'Our calls' : 'Simply buying']} labelFormatter={x => shortDate(String(x))}/><Line isAnimationActive={false} dataKey="model" stroke="#3972e2" strokeWidth={2.2} dot={false}/><Line isAnimationActive={false} dataKey="baseline" stroke="#a4afbf" strokeDasharray="5 4" dot={false}/>
          </ComposedChart></ResponsiveContainer> : <Empty title="Awaiting results"/>}
        </Panel>
        <Panel title="Rule scores vs results" subtitle="Predicted confidence compared with observed accuracy">
          {data.calibration.length ? <><div className="legend chart-legend"><span><i className="blue-dot"/>Rule score</span><span><i className="teal-dot"/>Observed</span></div><ResponsiveContainer width="100%" height={220}><BarChart data={data.calibration} margin={{right: 20, left: -15}}>
            <CartesianGrid vertical={false} strokeDasharray="3 5" stroke="#e9edf3"/><XAxis dataKey="label" tick={{fontSize: 11}} axisLine={false} tickLine={false}/><YAxis domain={[0, 100]} tickFormatter={n => `${n}%`} tick={{fontSize: 11}} axisLine={false} tickLine={false}/><Tooltip formatter={(v, n) => [`${v}%`, n === 'expected' ? 'Rule score' : 'Observed']}/><Bar isAnimationActive={false} dataKey="expected" fill="#79a0f0" radius={[4, 4, 0, 0]}/><Bar isAnimationActive={false} dataKey="actual" fill="#80c6b6" radius={[4, 4, 0, 0]}/>
          </BarChart></ResponsiveContainer><p className="panel-footnote">{data.calibration.map(x => `${x.label}: ${x.count} calls`).join(' · ')}</p></> : <Empty title="Awaiting results"/>}
        </Panel>
      </div>
      {data.groups.map(group => <div className="group-row" key={group.name}><div><strong>{group.name}</strong><small>{group.total} scored calls</small></div><div><strong>{group.accuracy ?? '—'}% right</strong><small>Simply buying: {group.baseline_accuracy ?? '—'}%</small></div><span className={tone(group.pnl)}>{money(group.pnl)}</span></div>)}
      {data.causes.length > 0 && <p className="panel-footnote">Loss review: {data.causes.map(cause => `${cause.name} (${cause.count})`).join(' · ')}</p>}
    </div></details>
  </>;
}

function HistoryPage({dates, open}: {dates: string[]; open: (call: Call) => void}) {
  const [date, setDate] = useState(dates[0] || ''), [wrong, setWrong] = useState(false), [direction, setDirection] = useState('all');
  const {data, error, loading, reload} = useApi<Dashboard>(`today?date=${date}`);
  useEffect(() => {if (!dates.includes(date)) setDate(dates[0] || '');}, [dates, date]);
  if (!dates.length) return <Empty title="No saved calls yet"/>;
  const index = dates.indexOf(date);
  return <>
    <div className="history-controls"><div className="date-picker">
      <button className="icon-button" aria-label="Previous trading day" disabled={index >= dates.length - 1} onClick={() => setDate(dates[index + 1])}><ChevronLeft size={18}/></button><CalendarDays size={17}/>
      <select aria-label="Trading day" value={date} onChange={e => setDate(e.target.value)}>{dates.map(day => <option key={day} value={day}>{fullDate(day)}</option>)}</select>
      <button className="icon-button" aria-label="Next trading day" disabled={index <= 0} onClick={() => setDate(dates[index - 1])}><ChevronRight size={18}/></button>
    </div><div className="segmented">{['all', 'UP', 'DOWN'].map(value => <button className={direction === value ? 'selected' : ''} onClick={() => setDirection(value)} key={value}>{value === 'all' ? 'All calls' : value === 'UP' ? 'Buy' : 'Sell'}</button>)}</div>
      <label className="switch-label"><input type="checkbox" checked={wrong} onChange={e => setWrong(e.target.checked)}/><span className="switch"/>Only wrong calls</label>
    </div>
    {error ? <Failure message={error} retry={reload}/> : loading || !data ? <Loading/> : <>
      <Panel title={`${data.calls.length} ${data.calls.length === 1 ? 'call' : 'calls'} on the record`} subtitle="₹1,000 per stock · comparison on the same names"><CallsTable calls={data.calls.filter(call => (!wrong || call.result === 'Wrong') && (direction === 'all' || call.direction === direction))} open={open}/></Panel>
      <div className="two-columns">{['morning', 'evening'].map(period => <details className="panel section-disclosure" key={period}><summary>{period === 'morning' ? 'Morning note' : 'Evening note'}</summary><Brief date={date} period={period}/></details>)}</div>
    </>}
  </>;
}
function Brief({date, period}: {date: string; period: string}) {
  const {data, error, loading, reload} = useApi<{text: string; html?: string}>(`brief/${period}?date=${date}`);
  return error ? <Failure message={error} retry={reload}/> : loading ? <p className="pad muted">Loading note…</p> : <TelegramPreview html={data?.html} text={data?.text}/>;
}

function StockPage({open, initial}: {open: (call: Call) => void; initial: string}) {
  const [query, setQuery] = useState(''), [selected, setSelected] = useState(initial || 'RELIANCE');
  const {data: stocks} = useApi<{symbol: string; name: string; sector: string}[]>('stocks');
  const {data, error, loading, reload} = useApi<Stock>(`stocks/${selected}`);
  const matches = (stocks || []).filter(stock => `${stock.symbol} ${stock.name}`.toLowerCase().includes(query.toLowerCase()));
  return <>
    <div className="stock-search-wrap"><Search size={20}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search stocks" aria-label="Find a stock"/>
      {query && <div className="search-results">{matches.length ? matches.map(stock => <button key={stock.symbol} onClick={() => {setSelected(stock.symbol); setQuery('');}}><strong>{stock.symbol}</strong><span>{stock.name}</span><ArrowRight size={15}/></button>) : <p>No matching stock</p>}</div>}
    </div>
    <div className="quick-stocks">{['RELIANCE', 'TCS', 'HDFCBANK', 'NIFTY'].filter(symbol => stocks?.some(stock => stock.symbol === symbol)).map(symbol => <button className={selected === symbol ? 'active' : ''} onClick={() => setSelected(symbol)} key={symbol}>{symbol}</button>)}</div>
    {error ? <Failure message={error} retry={reload}/> : loading || !data ? <Loading/> : <>
      <div className="stock-title"><Avatar symbol={selected}/><div><h2>{data.name}</h2><span>{selected} · {data.sector}</span></div><Badge tint="blue">{data.calls.length} calls</Badge></div>
      <Metrics summary={data.summary} showTotal/>
      <Panel title="Price history" subtitle="Call outcomes: green = right · red = wrong">
        {data.prices.length ? <div className="chart"><ResponsiveContainer width="100%" height={280}><ComposedChart data={data.prices.map(value => {
          const call = data.calls.find(call => call.date === value.date);
          return {...value, right: call?.result === 'Right' ? value.close : null, wrong: call?.result === 'Wrong' ? value.close : null};
        })} margin={{top: 15, right: 20, left: 10}}>
          <CartesianGrid vertical={false} strokeDasharray="3 5" stroke="#e9edf3"/><XAxis dataKey="date" tickFormatter={shortDate} minTickGap={65} tick={{fontSize: 11}} axisLine={false} tickLine={false}/><YAxis domain={['auto', 'auto']} tickFormatter={n => `₹${Math.round(n)}`} tick={{fontSize: 11}} axisLine={false} tickLine={false}/><Tooltip formatter={value => price(Number(value))} labelFormatter={label => shortDate(String(label))}/><Line isAnimationActive={false} dataKey="close" name="Close" stroke="#7197df" dot={false} strokeWidth={2}/><Scatter isAnimationActive={false} dataKey="right" name="Right" fill="#24977d"/><Scatter isAnimationActive={false} dataKey="wrong" name="Wrong" fill="#d97176"/>
        </ComposedChart></ResponsiveContainer></div> : <Empty title="No price history"/>}
      </Panel>
      <EventNotes symbol={selected} notes={data.events || []} patterns={data.patterns || []} options={data.event_options || {event_types: [], effects: []}} onSaved={reload}/>
      <details className="panel section-disclosure"><summary>All research calls · {data.calls.length}</summary><p className="panel-footnote">Includes candidates outside the daily shortlist.</p><CallsTable calls={data.calls} open={open}/></details>
      <details className="panel section-disclosure"><summary>Stock performance vs simply buying</summary><Legend/><MoneyChart points={data.summary.equity}/></details>
    </>}
  </>;
}

function HealthPage({toast}: {toast: (text: string) => void}) {
  const {data, error, loading, reload} = useApi<Health>('health');
  const [busy, setBusy] = useState<number | null>(null);
  async function decide(id: number, decision: string) {
    setBusy(id);
    try {const result = await api<{message: string}>(`improvements/${id}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({decision})}); toast(result.message); reload();}
    catch (e) {toast((e as Error).message);} finally {setBusy(null);}
  }
  if (error) return <Failure message={error} retry={reload}/>;
  if (loading || !data) return <Loading/>;
  const checks = data.checks.filter(check => !['AI helpers', 'F&O'].includes(check.name));
  return <>
    <div className="health-grid">{checks.map(check => <div className="health-card" key={check.name}>
      <div><span className={`status-dot ${check.status}`}/><h3>{check.name}</h3><Badge tint={check.status === 'ok' ? 'green' : check.status === 'bad' ? 'red' : 'neutral'}>{check.status === 'ok' ? 'OK' : check.status === 'bad' ? 'Action required' : 'Review'}</Badge></div><p>{check.detail}</p>
    </div>)}</div>
    <Panel title="Recent jobs">
      {data.jobs.length ? <div className="table-scroll"><table><thead><tr><th>Job</th><th>Status</th><th>Rows</th><th>Details</th></tr></thead><tbody>{data.jobs.map((job, index) => <tr key={index}>
        <td><strong>{job.name}</strong><span className="cell-sub">{new Date(job.at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'})} IST</span></td><td><Badge tint={job.status === 'ok' ? 'green' : 'neutral'}>{job.status}</Badge></td><td>{job.rows.toLocaleString()}</td><td>{job.detail}</td>
      </tr>)}</tbody></table></div> : <Empty title="No jobs recorded"/>}
    </Panel>
    <details className="panel section-disclosure"><summary>Method and experiments</summary><div className="details-body">
      <h3>Five-day trend rule</h3><p className="method-summary">Uncalibrated price-based scores. News notes are recorded separately and do not affect calls.</p>
      {data.models.map(model => <div className="model-item" key={model.name}><FlaskConical size={18}/><div><strong>{model.name}</strong><p>{model.description}</p><small>{model.status} · {shortDate(model.date.slice(0, 10))}</small></div></div>)}
      {data.ideas.length > 0 && <><h3>Experiment backlog</h3><p className="method-summary">Queued ideas do not change the active rule.</p><div className="idea-list">{data.ideas.map(idea => <div className="idea" key={idea.id}>
        <span className="idea-symbol"><Sparkles size={18}/></span><div><h3>{idea.title}</h3><p>{idea.detail}</p></div>
        {idea.status === 'pending' ? <div className="idea-actions"><button className="button secondary small" disabled={busy === idea.id} onClick={() => void decide(idea.id, 'skipped')}>Skip</button><button className="button primary small" disabled={busy === idea.id} onClick={() => void decide(idea.id, 'queued')}>Try it <ArrowRight size={14}/></button></div> : <Badge tint={idea.status === 'queued' ? 'blue' : 'neutral'}>{idea.status === 'queued' ? 'Queued' : 'Skipped'}</Badge>}
      </div>)}</div></>}
    </div></details>
  </>;
}

function Modal({children, title, close, drawer = false}: {children: ReactNode; title: string; close: () => void; drawer?: boolean}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement, overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden'; ref.current?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
      if (event.key === 'Tab') {
        const elements = Array.from(ref.current?.querySelectorAll<HTMLElement>('button,a[href],input,select,textarea,summary,[tabindex="0"]') || []).filter(element => element.getClientRects().length && !element.hasAttribute('disabled'));
        const first = elements[0], last = elements[elements.length - 1];
        if (!first) event.preventDefault();
        else if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) {event.preventDefault(); last?.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
      }
    };
    document.addEventListener('keydown', key);
    return () => {document.body.style.overflow = overflow; document.removeEventListener('keydown', key); previous?.focus();};
  }, [close]);
  return <div className={`modal-overlay ${drawer ? 'drawer-overlay' : ''}`} onMouseDown={event => {if (event.target === event.currentTarget) close();}}>
    <div ref={ref} className={drawer ? 'drawer' : 'modal'} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
      <div className="modal-head"><h2>{title}</h2><button className="icon-button" aria-label="Close details" onClick={close}><X size={21}/></button></div>{children}
    </div>
  </div>;
}
function CallDrawer({call, close, lookup}: {call: Call; close: () => void; lookup: (symbol: string) => void}) {
  return <Modal title="Call details" close={close} drawer><div className="drawer-body">
    <div className="stock-title"><Avatar symbol={call.symbol}/><div><h2>{call.symbol}</h2><span>{call.name}</span></div><Badge tint={call.direction === 'UP' ? 'green' : 'red'}>{call.direction === 'UP' ? 'Buy' : 'Sell'}</Badge></div>
    <p className="muted small-text">{fullDate(call.date)} · {call.sample ? 'Generated example' : 'Recorded forecast'}</p>
    <div className="drawer-confidence"><span>Rule score</span><strong>{call.confidence}%</strong><p>{call.past_total ? `Earlier calls: ${call.past_right} / ${call.past_total} right` : 'No earlier resolved calls'}</p></div>
    <h3>Reason</h3><p className="reason">{call.reason}</p>
    <div className="detail-grid"><div><span>Closing range</span><strong>{level(call, call.expected_low)} – {level(call, call.expected_high)}</strong></div><div><span>Alert level</span><strong>{level(call, call.stop)}</strong></div><div><span>Previous close</span><strong>{level(call, call.ref_price)}</strong></div><div><span>Horizon</span><strong>Open → close</strong></div></div>
    <h3>Result</h3><div className="result-detail"><Result call={call}/><strong className={tone(call.pnl)}>{call.kind === 'index' ? 'Direction only' : money(call.pnl)}</strong></div>
    {call.result === 'Pending' ? <p className="muted">Awaiting closing prices.</p> : <><div className="day-detail"><span>Open / close</span><strong>{level(call, call.entry!)} / {level(call, call.exit!)}</strong></div><div className="day-detail"><span>Simply buying</span><strong>{money(call.baseline_pnl)}</strong></div>{call.explanation && <p className="miss-explanation">{call.explanation}</p>}</>}
    <details className="call-provenance"><summary>Sources and record details</summary>
      <p className="method-summary">{call.model} · scores are uncalibrated. Alerts are levels, not simulated fills.</p>
      <div className="sources">{call.sources.map((source, index) => <div key={index}>
        {source.url && /^https?:\/\//.test(source.url) ? <a href={source.url} target="_blank" rel="noreferrer">{source.label}<ExternalLink size={13}/></a> : <span>{source.label}</span>}
        <small>{new Date(source.published_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'})} IST</small>
      </div>)}</div><div className="frozen-note"><LockKeyhole size={14}/>Original call saved. It cannot be edited.</div>
    </details>
    <button className="button primary full" onClick={() => lookup(call.symbol)}>See every call on {call.symbol}<ArrowRight size={15}/></button>
  </div></Modal>;
}
function MethodDetails() {
  return <div className="method-content">
    <div><span>01</span><section><h3>Selection</h3><p>Up to ten available candidates, ranked across Buy and Sell with no direction quota. The five-day trend rule is uncalibrated; a rule score is not an established success rate. Older calls retain their original selection.</p></section></div>
    <div><span>02</span><section><h3>Scoring</h3><p>Open-to-close returns on ₹1,000 per stock, less 0.15% assumed trading costs. Long and short returns use the entry price as denominator. Indices are scored for direction only. The comparison uses fractional positions, not executable fills; alerts do not simulate stops.</p></section></div>
    <div><span>03</span><section><h3>Comparison</h3><p>Simply buying uses the exact same stocks, allocation and costs. All resolved calls, including losses, remain in the record. Missing closes stay pending.</p></section></div>
    <div><span>04</span><section><h3>Data</h3><p>Morning inputs must be published and received by 07:00 IST. Saved calls and results cannot be rewritten. News is context only. Generated data is labelled; paper results do not represent real orders.</p></section></div>
  </div>;
}

export default function App() {
  const [page, setPage] = useState<Page>((nav.some(item => item.id === location.hash.slice(1)) ? location.hash.slice(1) : 'today') as Page);
  const [menu, setMenu] = useState(false), [call, setCall] = useState<Call | null>(null);
  const [modal, setModal] = useState<'method' | 'brief' | null>(null), [stock, setStock] = useState('RELIANCE'), [toast, setToast] = useState('');
  const {data, error, loading, reload} = useApi<Dashboard>('today', 60000);
  const close = useCallback(() => {setCall(null); setModal(null);}, []);
  const navigate = useCallback((next: Page) => {setPage(next); location.hash = next; setMenu(false); window.scrollTo({top: 0, behavior: 'instant'});}, []);
  useEffect(() => {
    const update = () => {const value = location.hash.slice(1); if (nav.some(item => item.id === value)) setPage(value as Page);};
    window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update);
  }, []);
  useEffect(() => {if (toast) {const timer = setTimeout(() => setToast(''), 5000); return () => clearTimeout(timer);}}, [toast]);
  const pageInfo = {
    today: {title: 'Daily overview', subtitle: 'Calls, market data and latest results.'},
    record: {title: 'Track record', subtitle: 'Results after costs, compared with simply buying.'},
    history: {title: 'Calls by day', subtitle: 'Saved calls and outcomes.'},
    stock: {title: 'Stock research', subtitle: 'Price history, company news and recorded calls.'},
    indices: {title: 'Index lab', subtitle: 'Nifty 50 and Bank Nifty.'},
    health: {title: 'System health', subtitle: 'Data sources, notifications and scheduled jobs.'},
  }[page];
  return <div className="app-shell">
    {menu && <div className="nav-scrim" onClick={() => setMenu(false)}/>}
    <aside className={`sidebar ${menu ? 'open' : ''}`}>
      <a className="brand" href="#today" onClick={() => navigate('today')}><span className="brand-mark"><BarChart3 size={23} strokeWidth={2.5}/></span><span>Nifty<span className="brand-light"> Signal</span><small>MARKET JOURNAL</small></span></a>
      <div className="nav-caption">WORKSPACE</div>
      <nav>{nav.map(item => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><item.icon size={19}/>{item.label}{page === item.id && <span className="nav-active-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><button className="help-button" onClick={() => setModal('method')}><CircleHelp size={18}/> Method & data</button><div className="profile"><span>RJ</span><div><strong>Ravi’s workspace</strong><small>Private journal</small></div><LockKeyhole size={14}/></div></div>
    </aside>
    <div className="workspace"><header className="topbar"><div><button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={menu} onClick={() => setMenu(value => !value)}><Menu size={22}/></button><span className="topbar-parent">Journal</span><ChevronRight size={13}/><strong>{nav.find(item => item.id === page)?.label}</strong></div>
      {data && <span className={`badge dataset-label ${data.mode === 'live' ? 'neutral' : 'blue'}`}><FlaskConical size={13}/>{data.mode === 'live' ? 'Paper journal' : 'Generated sample data'}</span>}
    </header><main>
      <div className="page-heading"><div><div className="eyebrow page-eyebrow">{data?.date ? fullDate(data.date) : 'MARKET JOURNAL'} <span>· IST</span></div><h1>{pageInfo.title}</h1><p>{pageInfo.subtitle}</p></div>
        <div className="heading-actions">{page === 'today' ? <button className="button secondary" disabled={!data?.date} onClick={() => setModal('brief')}><Send size={16}/>Morning note</button> : <button className="button secondary" onClick={() => void downloadCalls().catch(e => setToast(e.message))}><Download size={16}/>Export calls</button>}<button className="icon-button refresh-button" onClick={reload} aria-label="Refresh journal"><History size={17}/></button></div>
      </div>
      {error ? <Failure message={error} retry={reload}/> : loading || !data ? <Loading/> : page === 'today' ? <Today data={data} open={setCall} navigate={navigate}/> : page === 'record' ? <RecordPage/> : page === 'history' ? <HistoryPage dates={data.dates} open={setCall}/> : page === 'indices' ? <IndexLab/> : page === 'stock' ? <StockPage open={setCall} initial={stock}/> : <HealthPage toast={setToast}/>}
      <footer><span>Nifty Signal</span><span>All times IST</span></footer>
    </main></div>
    {call && <CallDrawer call={call} close={close} lookup={symbol => {setStock(symbol); close(); navigate('stock');}}/>}
    {modal && <Modal title={modal === 'method' ? 'Method & data' : 'Morning note · preview'} close={close}>
      {modal === 'brief' && data?.date ? <><p className="preview-caption">Preview only · not sent from this screen</p><Brief date={data.date} period="morning"/></> : <MethodDetails/>}
    </Modal>}
    {toast && <div className="toast" role="status"><CheckCheck size={18}/>{toast}<button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={16}/></button></div>}
  </div>;
}