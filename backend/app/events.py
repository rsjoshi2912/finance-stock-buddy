"""Event assessments and measured reactions.

Every article that names a tracked company gets a frozen, versioned assessment: what happened,
and the possible effect for that company over the next session. When the session bars arrive,
the observed reaction is written once beside it. Comparable earlier events are found only among
outcomes that were already known at the chosen cutoff, so no note can borrow from hindsight.

Nothing in this module changes a prediction. Text sentiment, event assessment and price
probability stay separate; news gains influence only after an evaluated challenger passes its gate.
"""
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

from sqlalchemy import select, true

from .config import ALLOCATION, COST_RATE
from .engine import utcstamp
from .ingest import now
from .market import IST, MarketError
from .models import EventAssessment, EventOutcome, Instrument, NewsArticle, Price

RULES_VERSION = 'rules_v2'
OWNER = 'owner'
EFFECTS = ('Positive', 'Negative', 'Neutral', 'Mixed', 'Unclear')
CONFIDENCES = ('low', 'medium', 'high')
HORIZON = 'next_session'
MINIMUM_CASES = 5
CLUSTER_DAYS = 3
CONFIRMED_SOURCES = ('NSE announcements', 'BSE announcements')
BENCHMARKS = ('NIFTY', 'NIFTY50')
TRADE = f'₹{ALLOCATION:,.0f} long from open to close, {COST_RATE * 100:.2f}% costs'

# Priority order matters: the first matching type is recorded as the primary event type.
TYPE_PATTERNS = (
    ('earnings', r'\b(q[1-4](\s*fy\s*\d{2,4})?|quarter(ly)?\s+(results?|profit|revenue|earnings|numbers)|net (profit|loss)|(profit|revenue|earnings|ebitda|sales)\s+(rises?|jumps?|surges?|climbs?|grows?|falls?|drops?|slumps?|plunges?|declines?|up|down)|results?\s+(today|announced|declared))\b'),
    ('guidance', r'\b(guidance|outlook|forecasts?|expects?\s+(revenue|growth|margins?|demand))\b'),
    ('regulation_legal', r'\b(sebi|court|lawsuit|penalt(y|ies)|probe|investigation|banned|ban on|show-?cause|tribunal|nclt|regulator)\b'),
    ('debt_credit', r'\b(debt|credit rating|rating (upgrade|downgrade|action)|downgrade[sd]?|upgrade[sd]?|defaults?|bonds?|ncds?|borrowings?)\b'),
    ('merger_financing', r'\b(merger|acquisitions?|acquires?|acquired|stake\s+(sale|purchase|in)|qip|ipo|fund-?rais(e|ing)|rights issue|preferential (issue|allotment)|takeover|demerger)\b'),
    ('corporate_action', r'\b(dividend|bonus (issue|shares?)|stock split|record date|ex-date|buy-?back)\b'),
    ('management_governance', r'\b(ceo|cfo|managing director|chairman|chairperson|resign(s|ed|ation)?|appoint(s|ed|ment)|steps down)\b'),
    ('order_contract', r'\b(orders?|contracts?|tender|letter of award|bags|wins|secures?)\b'),
    ('policy', r'\b(rbi|repo rate|monetary policy|budget|gst|tariffs?|government|ministry)\b'),
    ('commodity_currency', r'\b(crude|oil prices?|brent|rupee|dollar|commodit(y|ies)|steel prices?|coal prices?)\b'),
)
EVENT_TYPES = tuple(name for name, _ in TYPE_PATTERNS) + ('other',)
POSITIVE = r'\b(wins|bags|secures?|awarded|receives? (an? )?order|upgrade[sd]?|record (profit|revenue|high)|beats? (estimates|expectations)|(profit|revenue|sales) (rises?|jumps?|surges?|climbs?|grows?|up))\b'
NEGATIVE = r'\b(cancel(s|led|lation)?|terminat(es|ed|ion)|defaults?|downgrade[sd]?|penalt(y|ies)|fined?|probe|investigation|banned|loss widens|(profit|revenue|sales) (falls?|drops?|slumps?|plunges?|declines?|down)|misses? (estimates|expectations)|resign(s|ed|ation)|steps down|fraud|recall)\b'
NEUTRAL = r'\b(record date|ex-date|annual general meeting|agm|board meeting|investor (call|presentation)|analyst meet)\b'

def calendar_hours(session, provider):
    """Exchange hours for eligible-session lookups. An unreadable calendar reports unknown, never a guess."""
    from .market import market_session
    def hours(day):
        try: return market_session(session, provider, day)
        except MarketError: raise
        except Exception: raise MarketError(f'The exchange calendar could not be read for {day}.') from None
    return hours

def cues(pattern, text):
    return sorted({match.group(0).strip() for match in re.finditer(pattern, text)})

def classify(text):
    """Keyword rules over the supplied text only. Unmatched wording stays Unclear, never guessed."""
    lowered = ' ' + re.sub(r'\s+', ' ', (text or '').lower()) + ' '
    event_type = next((name for name, pattern in TYPE_PATTERNS if re.search(pattern, lowered)), 'other')
    found = dict(positive=cues(POSITIVE, lowered), negative=cues(NEGATIVE, lowered), neutral=cues(NEUTRAL, lowered))
    if found['positive'] and found['negative']: effect = 'Mixed'
    elif found['positive']: effect = 'Positive'
    elif found['negative']: effect = 'Negative'
    elif found['neutral']: effect = 'Neutral'
    else: effect = 'Unclear'
    if event_type in ('earnings', 'guidance') and effect in ('Positive', 'Negative'):
        # A reported number is not a surprise until it is compared with what was expected.
        effect = 'Unclear'
        found['note'] = 'A reported figure cannot be judged without the expectation that preceded it.'
    if re.search(r"\b(no|not|denies|denied|denial|rumou?rs?|unconfirmed|may|might|could)\b|n't\b", lowered):
        effect = 'Unclear'
        found['note'] = 'Negation or uncertain wording needs a human read; keyword matches cannot establish the effect.'
    return event_type, effect, found

def describe(article, found):
    parts = [f'Reported by {article.source}: {article.title.strip()}']
    words = found['positive'] + found['negative'] + found['neutral']
    if words: parts.append('Wording noted: ' + ', '.join(words) + '.')
    if found.get('note'): parts.append(found['note'])
    parts.append('No pre-release expectation is recorded.')
    return ' '.join(parts)

def eligible_session(published_at, hours, limit=15):
    """First exchange session whose open follows publication.

    hours(day) returns {'open', 'close'} (None values on a holiday) or raises MarketError.
    Returns (session date, published during a session) or (None, None) when the calendar is unknown.
    """
    published = datetime.fromisoformat(published_at).astimezone(IST)
    during = False
    for offset in range(limit):
        candidate = (published.date() + timedelta(days=offset)).isoformat()
        try: session = hours(candidate)
        except MarketError: return None, None
        if not session or not session.get('open'): continue
        opened = datetime.fromisoformat(session['open']).astimezone(IST)
        closed = datetime.fromisoformat(session['close']).astimezone(IST)
        if published < opened: return candidate, during
        if published <= closed: during = True
    return None, None

def assess_new_articles(session, hours=None, observed_at=None, limit=500):
    """Assess new articles; preserve earlier rule versions without relabelling old observations."""
    stamp = utcstamp(observed_at or now())
    assessed = select(EventAssessment.article_id).where(EventAssessment.assessor.like('rules_%'))
    articles = session.scalars(select(NewsArticle).where(NewsArticle.symbols != '[]', NewsArticle.id.not_in(assessed))
        .order_by(NewsArticle.id).limit(limit)).all()
    created = 0
    for article in articles:
        if article.received_at > stamp:
            raise ValueError('An article cannot be assessed before it was received')
        event_type, effect, found = classify(article.title + ' ' + article.body)
        symbols = json.loads(article.symbols)
        if len(symbols) > 1:
            effect = 'Unclear'
            found['note'] = 'Several companies are named; this rule cannot assign the same effect to each one.'
        eligible, during = eligible_session(article.published_at, hours) if hours else (None, None)
        for symbol in symbols:
            if not session.get(Instrument, symbol): continue
            session.add(EventAssessment(article_id=article.id, symbol=symbol, event_type=event_type, effect=effect,
                horizon=HORIZON, confidence='low', facts=describe(article, found), expectation=None,
                reliability='exchange_confirmed' if article.source in CONFIRMED_SOURCES else 'reported',
                assessor=RULES_VERSION, evidence_hash=article.content_hash, eligible_session=eligible,
                published_during_session=during, assessed_at=stamp))
            created += 1
    session.flush()
    return created

def record_owner_assessment(session, article_id, symbol, event_type, effect, facts, *, expectation=None,
                            confidence='medium', hours=None, observed_at=None):
    """The owner's own read of an article. It is a new version beside earlier ones, never a replacement."""
    article = session.get(NewsArticle, article_id)
    if not article: raise ValueError('Article not found')
    if not session.get(Instrument, symbol): raise ValueError('Stock not found')
    if event_type not in EVENT_TYPES: raise ValueError('Choose a listed event type')
    if effect not in EFFECTS: raise ValueError('Choose Positive, Negative, Neutral, Mixed or Unclear')
    if confidence not in CONFIDENCES: raise ValueError('Confidence must be low, medium or high')
    facts = re.sub(r'\s+', ' ', facts or '').strip()
    if not 10 <= len(facts) <= 2000: raise ValueError('Describe what happened in 10 to 2,000 characters')
    expectation = re.sub(r'\s+', ' ', expectation or '').strip()[:500] or None
    stamp = utcstamp(observed_at or now())
    if article.received_at > stamp: raise ValueError('An article cannot be assessed before it was received')
    eligible, during = eligible_session(article.published_at, hours) if hours else (None, None)
    row = EventAssessment(article_id=article.id, symbol=symbol, event_type=event_type, effect=effect, horizon=HORIZON,
        confidence=confidence, facts=facts, expectation=expectation,
        reliability='exchange_confirmed' if article.source in CONFIRMED_SOURCES else 'reported', assessor=OWNER,
        evidence_hash=article.content_hash, eligible_session=eligible, published_during_session=during, assessed_at=stamp)
    session.add(row); session.flush()
    return row

def pct(value, base):
    return round((value / base - 1) * 100, 3)

def benchmark_change(session, start_close_date, end_date, cutoff):
    for symbol in BENCHMARKS:
        index = session.get(Instrument, symbol)
        if not index or index.kind != 'index': continue
        before = session.scalar(select(Price).where(Price.symbol == symbol, Price.date == start_close_date))
        after = session.scalar(select(Price).where(Price.symbol == symbol, Price.date == end_date))
        if before and after and max(before.published_at, before.ingested_at, after.published_at, after.ingested_at) <= cutoff:
            return symbol, pct(after.close, before.close)
    return None, None

def session_dates(start, hours, count=5, step=1):
    """Verified consecutive sessions, never the next N available bars across a data gap."""
    if not hours: return []
    result = []
    for offset in range(31):
        day = (date.fromisoformat(start) + timedelta(days=offset * step)).isoformat()
        try: trading = hours(day)
        except MarketError: return []
        if trading and trading.get('open'):
            result.append(day)
            if len(result) == count: return result
    return []

def record_outcomes(session, hours=None, observed_at=None, limit=2000):
    """Write the session and five-session reactions once each, as soon as the bars exist."""
    stamp = utcstamp(observed_at or now())
    complete = select(EventOutcome.assessment_id).where(EventOutcome.horizon == 'five_sessions')
    rows = session.execute(select(EventAssessment, NewsArticle).join(NewsArticle, NewsArticle.id == EventAssessment.article_id)
        .where(EventAssessment.id.not_in(complete)).order_by(EventAssessment.id).limit(limit)).all()
    recorded = 0
    for assessment, article in rows:
        if max(assessment.assessed_at, article.received_at, article.published_at) > stamp: continue
        start = assessment.eligible_session
        if not start and hours: start, _ = eligible_session(article.published_at, hours)
        if not start: continue
        prior = session_dates((date.fromisoformat(start) - timedelta(days=1)).isoformat(), hours, count=1, step=-1)
        if not prior: continue
        before = session.scalar(select(Price).where(Price.symbol == assessment.symbol, Price.date == prior[0]))
        after = session.scalars(select(Price).where(Price.symbol == assessment.symbol, Price.date >= start).order_by(Price.date).limit(5)).all()
        if not before or not after or after[0].date != start: continue
        existing = {o.horizon for o in session.scalars(select(EventOutcome).where(EventOutcome.assessment_id == assessment.id))}
        first = after[0]
        if 'session' not in existing:
            available = max(before.ingested_at, before.published_at, first.ingested_at, first.published_at)
            if available <= stamp:
                symbol, change = benchmark_change(session, before.date, first.date, stamp)
                session.add(EventOutcome(assessment_id=assessment.id, horizon='session', start_date=start, end_date=first.date,
                    reference_close=before.close, open=first.open, close=first.close, gap_pct=pct(first.open, before.close),
                    session_pct=pct(first.close, first.open), change_pct=pct(first.close, before.close),
                    benchmark_symbol=symbol, benchmark_pct=change, bars_available_at=available, recorded_at=stamp))
                recorded += 1
        expected = session_dates(start, hours)
        if 'five_sessions' not in existing and len(after) == 5 and [x.date for x in after] == expected:
            last = after[-1]
            available = max([before.ingested_at, before.published_at] + [max(x.ingested_at, x.published_at) for x in after])
            if available <= stamp:
                symbol, change = benchmark_change(session, before.date, last.date, stamp)
                session.add(EventOutcome(assessment_id=assessment.id, horizon='five_sessions', start_date=start, end_date=last.date,
                    reference_close=before.close, open=None, close=last.close, gap_pct=None, session_pct=None,
                    change_pct=pct(last.close, before.close), benchmark_symbol=symbol, benchmark_pct=change,
                    bars_available_at=available, recorded_at=stamp))
                recorded += 1
    session.flush()
    return recorded

def cluster(rows):
    """Syndicated copies of one story count once: same company, type and effect within three days."""
    groups = defaultdict(list)
    for assessment, article, outcome in rows:
        groups[(assessment.symbol, assessment.event_type, assessment.effect)].append((article, outcome))
    events = []
    for (symbol, event_type, effect), items in groups.items():
        current = None
        for article, outcome in sorted(items, key=lambda x: x[0].published_at):
            published = datetime.fromisoformat(article.published_at)
            if current and (published - datetime.fromisoformat(current['first_published'])).days < CLUSTER_DAYS:
                current['articles'] += 1; continue
            current = dict(symbol=symbol, event_type=event_type, effect=effect, first_published=article.published_at,
                date=outcome.start_date, articles=1, session_pct=outcome.session_pct, gap_pct=outcome.gap_pct)
            events.append(current)
    return sorted(events, key=lambda x: x['date'])

def summarize_events(events, scope):
    moves = [e['session_pct'] for e in events]
    gaps = [e['gap_pct'] for e in events]
    threshold = COST_RATE * 100
    return dict(scope=scope, count=len(events), articles=sum(e['articles'] for e in events), trade=TRADE,
        first_date=events[0]['date'] if events else None, last_date=events[-1]['date'] if events else None,
        median_session_pct=round(median(moves), 2) if moves else None, median_gap_pct=round(median(gaps), 2) if gaps else None,
        worst_session_pct=round(min(moves), 2) if moves else None, best_session_pct=round(max(moves), 2) if moves else None,
        share_positive_after_costs=round(100 * sum(m > threshold for m in moves) / len(moves)) if moves else None,
        status='ok' if len(events) >= MINIMUM_CASES else 'Not enough history')

def comparable_events(session, symbol, event_type, effect, *, cutoff, minimum=MINIMUM_CASES, exclude_published=None):
    """Earlier events of the same kind whose reactions were already known at the cutoff.

    exclude_published removes the story being assessed: same company within the clustering window,
    so a note written after its own reaction arrived cannot count itself as history.
    """
    cutoff = utcstamp(cutoff)
    instrument = session.get(Instrument, symbol)
    base = (select(EventAssessment, NewsArticle, EventOutcome)
        .join(NewsArticle, NewsArticle.id == EventAssessment.article_id)
        .join(EventOutcome, (EventOutcome.assessment_id == EventAssessment.id) & (EventOutcome.horizon == 'session'))
        .where(EventAssessment.event_type == event_type, EventAssessment.effect == effect,
               EventAssessment.assessed_at <= cutoff, NewsArticle.published_at <= cutoff, NewsArticle.received_at <= cutoff,
               EventOutcome.bars_available_at <= cutoff, EventOutcome.recorded_at <= cutoff))
    if exclude_published:
        centre = datetime.fromisoformat(utcstamp(exclude_published))
        window = timedelta(days=CLUSTER_DAYS)
        base = base.where(~((EventAssessment.symbol == symbol)
            & (NewsArticle.published_at > (centre - window).isoformat(timespec='seconds'))
            & (NewsArticle.published_at < (centre + window).isoformat(timespec='seconds'))))
    scopes = [('this company', EventAssessment.symbol == symbol)]
    if instrument and instrument.sector and instrument.sector != 'Not classified':
        members = select(Instrument.symbol).where(Instrument.sector == instrument.sector, Instrument.kind == 'stock')
        scopes.append((f'{instrument.sector} companies', EventAssessment.symbol.in_(members)))
    scopes.append(('all tracked companies', true()))
    result = None
    for label, condition in scopes:
        result = summarize_events(cluster(session.execute(base.where(condition)).all()), label)
        if result['count'] >= minimum: return result
    return result

def outcome_payload(outcome):
    return dict(horizon=outcome.horizon, start_date=outcome.start_date, end_date=outcome.end_date,
        reference_close=outcome.reference_close, open=outcome.open, close=outcome.close, gap_pct=outcome.gap_pct,
        session_pct=outcome.session_pct, change_pct=outcome.change_pct, benchmark_symbol=outcome.benchmark_symbol,
        benchmark_pct=outcome.benchmark_pct, bars_available_at=outcome.bars_available_at)

def move_words(value):
    if value is None: return 'is not measured'
    if abs(value) < 0.005: return 'was flat'
    return f'{"rose" if value > 0 else "fell"} {abs(value):.1f}%'

def review_text(assessment, outcome):
    if not outcome: return None
    session_move = move_words(outcome.session_pct)
    gap = outcome.gap_pct
    gap_words = 'no gap at the open' if gap is None or abs(gap) < 0.005 else f'gapped {"up" if gap > 0 else "down"} {abs(gap):.1f}% at the open'
    expected = {'Positive': outcome.session_pct is not None and outcome.session_pct > 0,
                'Negative': outcome.session_pct is not None and outcome.session_pct < 0}.get(assessment.effect)
    joiner = ';' if expected is None else (', and' if expected else ', but')
    return f'{assessment.effect} read{joiner} the stock {session_move} from open to close and {gap_words}. This is one observed reaction, not proof of cause.'

def note_payload(session, assessment, article, cutoff):
    outcomes = {o.horizon: o for o in session.scalars(select(EventOutcome).where(EventOutcome.assessment_id == assessment.id,
        EventOutcome.bars_available_at <= cutoff, EventOutcome.recorded_at <= cutoff))}
    before = comparable_events(session, assessment.symbol, assessment.event_type, assessment.effect,
        cutoff=assessment.assessed_at, exclude_published=article.published_at)
    unknowns = []
    if assessment.expectation is None: unknowns.append('No pre-release expectation was available, so surprise cannot be judged.')
    if assessment.reliability == 'reported': unknowns.append('Reported by a publisher; not an exchange filing.')
    if assessment.assessor.startswith('rules_'): unknowns.append('Labelled by keyword rules, not by a validated model.')
    unknowns.append('History groups same-company, same-type, same-effect stories within three days. Distinct events can be grouped together.')
    if before['status'] != 'ok': unknowns.append(f"Not enough comparable history ({before['count']} earlier case{'s' if before['count'] != 1 else ''} known when assessed).")
    if assessment.eligible_session is None: unknowns.append('The session calendar was unavailable when assessed; the reaction window is unknown.')
    why = [f'Event type: {assessment.event_type.replace("_", " ")}.', f'Source reliability: {assessment.reliability.replace("_", " ")}.']
    if assessment.expectation: why.append(f'What was expected: {assessment.expectation}')
    already = ('Published during a trading session. The move before that close happened before the measured next-session reaction.'
               if assessment.published_during_session else None)
    return dict(id=assessment.id, symbol=assessment.symbol, article=dict(id=article.id, title=article.title, url=article.url,
            source=article.source, published_at=article.published_at, received_at=article.received_at, time_basis=article.time_basis),
        event_type=assessment.event_type, effect=assessment.effect, horizon=assessment.horizon, confidence=assessment.confidence,
        assessor=assessment.assessor, reliability=assessment.reliability, assessed_at=assessment.assessed_at,
        eligible_session=assessment.eligible_session, published_during_session=assessment.published_during_session,
        what_happened=assessment.facts, why_it_matters=why, before=before, already_moved=already, unknowns=unknowns,
        outcome={k: outcome_payload(v) for k, v in outcomes.items()} or None, review=review_text(assessment, outcomes.get('session')),
        influences_predictions=False)

def event_notes(session, symbol, cutoff=None, limit=12):
    """Plain-language notes for one stock, newest first. Comparisons use only what was known when each note was written."""
    cutoff = utcstamp(cutoff or now())
    rows = session.execute(select(EventAssessment, NewsArticle).join(NewsArticle, NewsArticle.id == EventAssessment.article_id)
        .where(EventAssessment.symbol == symbol, EventAssessment.assessed_at <= cutoff)
        .order_by(EventAssessment.id.desc()).limit(limit)).all()
    return [note_payload(session, assessment, article, cutoff) for assessment, article in rows]

def history_summary(session, symbol, cutoff=None):
    """This company's completed events grouped by type and effect, using everything known at the cutoff."""
    cutoff = utcstamp(cutoff or now())
    rows = session.execute(select(EventAssessment, NewsArticle, EventOutcome)
        .join(NewsArticle, NewsArticle.id == EventAssessment.article_id)
        .join(EventOutcome, (EventOutcome.assessment_id == EventAssessment.id) & (EventOutcome.horizon == 'session'))
        .where(EventAssessment.symbol == symbol, EventAssessment.assessed_at <= cutoff,
               NewsArticle.published_at <= cutoff, NewsArticle.received_at <= cutoff,
               EventOutcome.bars_available_at <= cutoff, EventOutcome.recorded_at <= cutoff)).all()
    groups = defaultdict(list)
    for event in cluster(rows): groups[(event['event_type'], event['effect'])].append(event)
    return [dict(event_type=t, effect=e, **summarize_events(sorted(items, key=lambda x: x['date']), 'this company'))
            for (t, e), items in sorted(groups.items(), key=lambda kv: -len(kv[1]))]

def article_labels(session, article_ids):
    """Effect labels per article for the news list. Display only; never a signal."""
    if not article_ids: return {}
    labels = defaultdict(list)
    for a in session.scalars(select(EventAssessment).where(EventAssessment.article_id.in_(article_ids)).order_by(EventAssessment.id)):
        labels[a.article_id].append(dict(symbol=a.symbol, event_type=a.event_type, effect=a.effect, assessor=a.assessor))
    return labels
