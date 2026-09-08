import { useState } from 'react';
import type { FormEvent } from 'react';
import { Lightbulb } from 'lucide-react';
import { api } from './api';
import type { Comparison, EventNote, EventOptions, Pattern } from './types';

const TINT: Record<string, string> = {Positive: 'green', Negative: 'red', Mixed: 'amber', Neutral: 'neutral', Unclear: 'neutral'};
const pct = (value: number | null | undefined) => value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
const words = (value: string) => value.replace(/_/g, ' ');
const when = (iso: string) => new Date(iso).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'}) + ' IST';

function beforeText(before: Comparison) {
  if (before.status !== 'ok') {
    return `Not enough history. ${before.count} comparable ${before.scope} event${before.count === 1 ? '' : 's'} known when this note was written; at least 5 are needed before a pattern is shown.`;
  }
  return `${before.count} earlier ${before.scope} events (${before.first_date} to ${before.last_date}): median ${pct(before.median_session_pct)} from open to close, ` +
    `median gap ${pct(before.median_gap_pct)} at the open, worst ${pct(before.worst_session_pct)}, best ${pct(before.best_session_pct)}. ` +
    `${before.share_positive_after_costs}% paid after costs for ${before.trade}. A past share is not a probability for today.`;
}

function OwnerForm({note, options, onSaved, onCancel}: {note: EventNote; options: EventOptions; onSaved: () => void; onCancel: () => void}) {
  const [effect, setEffect] = useState('Unclear');
  const [eventType, setEventType] = useState(note.event_type);
  const [facts, setFacts] = useState('');
  const [expectation, setExpectation] = useState('');
  const [confidence, setConfidence] = useState('medium');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError('');
    try {
      await api(`events/${note.article.id}/assessment`, {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({symbol: note.symbol, event_type: eventType, effect, facts, expectation: expectation || null, confidence})});
      onSaved();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save the note.'); }
    finally { setSaving(false); }
  }
  return <form className="note-form" onSubmit={e => void submit(e)} aria-label="Add your own read">
    <label>Possible effect<select value={effect} onChange={e => setEffect(e.target.value)}>{options.effects.map(x => <option key={x}>{x}</option>)}</select></label>
    <label>Event type<select value={eventType} onChange={e => setEventType(e.target.value)}>{options.event_types.map(x => <option key={x} value={x}>{words(x)}</option>)}</select></label>
    <label>Confidence<select value={confidence} onChange={e => setConfidence(e.target.value)}>{['low', 'medium', 'high'].map(x => <option key={x}>{x}</option>)}</select></label>
    <label className="wide">What happened, in your words (facts only, 10 to 2,000 characters)<textarea value={facts} onChange={e => setFacts(e.target.value)} required minLength={10} maxLength={2000}/></label>
    <label className="wide">What was expected beforehand, if you know (optional)<input value={expectation} onChange={e => setExpectation(e.target.value)} maxLength={500}/></label>
    <div className="actions">
      <button className="button primary small" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save as a new note'}</button>
      <button className="button secondary small" type="button" onClick={onCancel}>Cancel</button>
      {error && <span className="negative small-text" role="alert">{error}</span>}
    </div>
  </form>;
}

export default function EventNotes({symbol, notes, patterns, options, onSaved}: {symbol: string; notes: EventNote[]; patterns: Pattern[]; options: EventOptions; onSaved: () => void}) {
  const [draft, setDraft] = useState<number | null>(null);
  return <section className="panel event-notes">
    <div className="panel-head"><div><h2><Lightbulb size={16}/> What the news says about {symbol}</h2>
      <p>Each note is frozen when it is written and never changes a call. It is here so you can see what followed.</p></div></div>
    {patterns.length > 0 && <div className="pattern-strip">{patterns.map(p => <div className="pattern" key={`${p.event_type}-${p.effect}`}>
      <strong>{words(p.event_type)} · {p.effect}</strong>
      <span>{p.count} event{p.count === 1 ? '' : 's'} on this stock{p.status !== 'ok' ? ' · Not enough history. At least 5 cases are needed.' : ` · median ${pct(p.median_session_pct)} open to close · ${p.share_positive_after_costs}% paid after costs`}</span>
    </div>)}</div>}
    {notes.length ? <div className="note-list">{notes.map(n => <article key={n.id} className="event-note">
      <header>
        <span className={`badge ${TINT[n.effect] || 'neutral'}`}>{n.effect}</span>
        <span className="badge blue">{words(n.event_type)}</span>
        <small>{n.assessor === 'owner' ? 'Your read' : 'Keyword rule'} · {n.confidence} confidence · noted {when(n.assessed_at)}</small>
      </header>
      <a href={n.article.url} target="_blank" rel="noopener noreferrer">{n.article.title}</a>
      <small>{n.article.source} · published {when(n.article.published_at)} · received {when(n.article.received_at)}</small>
      <dl className="note-grid">
        <div><dt>What happened</dt><dd>{n.what_happened}</dd></div>
        <div><dt>Possible effect</dt><dd>{n.effect} for {n.symbol} over the next session{n.eligible_session ? ` (${n.eligible_session})` : ' (session unknown)'}. {n.why_it_matters.join(' ')}</dd></div>
        <div><dt>What happened before</dt><dd>{beforeText(n.before)}</dd></div>
        {n.already_moved && <div><dt>Already moved?</dt><dd>{n.already_moved}</dd></div>}
        <div><dt>What we don’t know</dt><dd><ul>{n.unknowns.map(u => <li key={u}>{u}</li>)}</ul></dd></div>
        <div><dt>What actually happened</dt><dd>{n.review || 'Waiting for the session to finish. Nothing is guessed in the meantime.'}
          {n.outcome?.five_sessions && <> Five sessions later the stock was {pct(n.outcome.five_sessions.change_pct)} from the close before the event{n.outcome.five_sessions.benchmark_symbol ? ` (${n.outcome.five_sessions.benchmark_symbol} ${pct(n.outcome.five_sessions.benchmark_pct)})` : ''}.</>}</dd></div>
      </dl>
      {draft === n.id ? <OwnerForm note={n} options={options} onSaved={() => {setDraft(null); onSaved();}} onCancel={() => setDraft(null)}/>
        : <button className="button secondary small" onClick={() => setDraft(n.id)}>Add your own read</button>}
    </article>)}</div>
    : <p className="quote-note">No collected news has named this company yet. Notes appear once the public feeds mention it by name.</p>}
  </section>;
}
