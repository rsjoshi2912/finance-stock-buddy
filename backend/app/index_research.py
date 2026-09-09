"""Versioned index paper research. Never reads or writes the cash prediction tables."""
import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone, time

from sqlalchemy import select

from .engine import utcstamp
from .index_options import assess_option, paper_limits
from .index_sources import INDICES, OptionSource, index_candles
from .market import IST, MarketError, market_session
from .models import IndexAssessment, IndexCandle, Setting
from .public_data import YFinance

STRATEGY = 'index_orb_retest_v1'
SOURCE = 'Yahoo Finance'
INTERVAL = timedelta(minutes=5)
MAX_AGE = timedelta(minutes=10)


def clock(): return datetime.now(timezone.utc)


def hours_for(session, provider):
    cache = {}
    def hours(day):
        if day not in cache: cache[day] = market_session(session, provider, day)
        return cache[day]
    return hours


def ingest_candles(session, symbol, rows, received_at, hours):
    if not rows: return 0
    stamp = utcstamp(received_at)
    cutoff = datetime.fromisoformat(stamp)
    earliest = min(utcstamp(row['start_at']) for row in rows)
    latest = {}
    revisions = session.execute(select(IndexCandle.start_at, IndexCandle.content_hash).where(IndexCandle.symbol == symbol,
        IndexCandle.source == SOURCE, IndexCandle.start_at >= earliest).order_by(IndexCandle.id.desc()))
    for start, digest in revisions: latest.setdefault(start, digest)
    added = 0
    for row in rows:
        start = datetime.fromisoformat(utcstamp(row['start_at']))
        end = start + INTERVAL
        if end > cutoff: continue  # A still-forming candle is never a feature.
        local = start.astimezone(IST)
        schedule = hours(local.date().isoformat())
        if not schedule.get('open'): continue
        opened, closed = (datetime.fromisoformat(schedule[k]) for k in ('open','close'))
        if start < opened or end > closed or (start - opened).total_seconds() % 300: continue
        prices = [row[k] for k in ('open','high','low','close')]
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x <= 0 for x in prices):
            raise MarketError('An index candle contained an invalid price.')
        o, h, l, c = prices
        if not l <= min(o,c) <= max(o,c) <= h: raise MarketError('An index candle had inconsistent high/low prices.')
        start_text, end_text = utcstamp(start.isoformat()), utcstamp(end.isoformat())
        digest = hashlib.sha256(json.dumps([symbol, start_text, *prices], separators=(',',':')).encode()).hexdigest()
        if latest.get(start_text) == digest: continue
        session.add(IndexCandle(symbol=symbol, source=SOURCE, start_at=start_text, end_at=end_text,
            open=o, high=h, low=l, close=c, received_at=stamp, content_hash=digest))
        latest[start_text] = digest; added += 1
    session.flush()
    return added


def feature_candles(session, symbol, cutoff):
    cutoff = utcstamp(cutoff)
    rows = session.scalars(select(IndexCandle).where(IndexCandle.symbol == symbol, IndexCandle.source == SOURCE,
        IndexCandle.received_at <= cutoff, IndexCandle.end_at <= cutoff)
        .order_by(IndexCandle.start_at.desc(), IndexCandle.id.desc()).limit(2000)).all()
    chosen = {}
    for row in rows: chosen.setdefault(row.start_at, row)
    return sorted(chosen.values(), key=lambda row: row.start_at)


def expected_tail(last_start, hours, count=150):
    expected = []
    last = datetime.fromisoformat(last_start)
    day = last.astimezone(IST).date()
    for offset in range(10):
        schedule = hours((day - timedelta(days=offset)).isoformat())
        if not schedule.get('open'): continue
        opened, closed = (datetime.fromisoformat(schedule[k]) for k in ('open','close'))
        end = min(last + INTERVAL, closed)
        while end - INTERVAL >= opened:
            expected.append(utcstamp((end - INTERVAL).isoformat()))
            if len(expected) == count: return list(reversed(expected))
            end -= INTERVAL
    return []


def ema(values, period):
    result = [values[0]]
    alpha = 2 / (period + 1)
    for value in values[1:]: result.append(value * alpha + result[-1] * (1 - alpha))
    return result


def evaluate_index(symbol, bars, current, hours):
    local = current.astimezone(IST)
    result = dict(symbol=symbol, name=INDICES[symbol]['name'], direction='SKIP', reason='', strategy=STRATEGY,
        assessed_at=utcstamp(current.isoformat()), candle_at=bars[-1].end_at if bars else None,
        price=bars[-1].close if bars else None, opening_high=None, opening_low=None,
        trend=None, invalidation=None, valid_until=None, candle_ids=[], mode='paper', validated=False,
        horizon='Next 15 minutes; direction study only', source=SOURCE, may_be_delayed=True,
        news_used=False, news_note='News and scheduled event risk are not evaluated by this price-only rule.')
    def skip(reason): result['reason'] = reason; return result
    schedule = hours(local.date().isoformat())
    if not schedule.get('open'): return skip('The exchange is closed today.')
    opened, closed = (datetime.fromisoformat(schedule[k]) for k in ('open','close'))
    if not opened <= current < closed: return skip('Market closed. Refresh during the trading session.')
    if opened.astimezone(IST).time() != time(9,15) or closed.astimezone(IST).time() != time(15,30):
        return skip('This rule has not been tested for special trading hours.')
    if local.time() < time(9,40): return skip('Wait for the opening range, a break and a completed retest after 09:40 IST.')
    if local.time() >= time(14,45): return skip('No new paper entries after 14:45 IST.')
    if not bars: return skip('No completed index candles are available.')
    last_end = datetime.fromisoformat(bars[-1].end_at)
    if last_end > current or current - last_end >= MAX_AGE: return skip('Index candles are old. A fresh completed candle is required.')
    by_start = {bar.start_at:bar for bar in bars}
    required = expected_tail(bars[-1].start_at, hours)
    today_starts = [utcstamp((opened + i * INTERVAL).isoformat()) for i in range(int((last_end - opened) / INTERVAL))]
    if not required or any(key not in by_start for key in set(required + today_starts)):
        return skip('A five-minute candle is missing. Waiting for a complete opening range and trend history.')
    opening = [by_start[key] for key in today_starts[:3]]
    if len(opening) != 3: return skip('The first 15 minutes are incomplete.')
    high, low = max(b.high for b in opening), min(b.low for b in opening)
    values = [by_start[key].close for key in required]
    fast, slow = ema(values,20), ema(values,50)
    previous, breakout, retest = [by_start[key] for key in required[-3:]]
    result.update(opening_high=high, opening_low=low,
        trend='Rising' if fast[-1] > slow[-1] and fast[-1] > fast[-2] else 'Falling' if fast[-1] < slow[-1] and fast[-1] < fast[-2] else 'Mixed',
        candle_ids=[by_start[key].id for key in sorted(set(required + today_starts))])
    tolerance = .0005
    up = (previous.close <= high < breakout.close and high * (1 - tolerance) <= retest.low <= high * (1 + tolerance)
          and retest.close > high and retest.close > retest.open and result['trend'] == 'Rising' and retest.close > fast[-1])
    down = (previous.close >= low > breakout.close and low * (1 - tolerance) <= retest.high <= low * (1 + tolerance)
            and retest.close < low and retest.close < retest.open and result['trend'] == 'Falling' and retest.close < fast[-1])
    if not up and not down: return skip('No confirmed break and immediate retest with a matching trend. Wait.')
    result.update(direction='UP' if up else 'DOWN', invalidation=retest.low if up else retest.high,
        reason='The opening-range break held its next five-minute retest and the trend agrees. Unvalidated paper setup.')
    # Last entry time is 14:45 IST irrespective of the server timezone.
    result['valid_until'] = min(last_end + MAX_AGE, datetime.combine(local.date(),time(14,45),IST)).astimezone(timezone.utc).isoformat(timespec='seconds')
    return result


def save_assessment(session, payload):
    row = IndexAssessment(symbol=payload['symbol'], assessed_at=payload['assessed_at'], candle_at=payload.get('candle_at'),
        direction=payload['direction'], option_action=payload['option']['action'], payload=json.dumps(payload,allow_nan=False))
    session.add(row); session.flush()
    return row


def collect_and_assess(session, provider=None):
    owns_provider = provider is None
    provider = provider or YFinance()
    hours = hours_for(session, provider)
    results = []
    try:
        for symbol in INDICES:
            try:
                rows = index_candles(provider, symbol)
                received = clock()  # Never the scheduler tick/request-start timestamp.
                with session.begin_nested():
                    added = ingest_candles(session, symbol, rows, received.isoformat(), hours)
                current = clock()
                bars = feature_candles(session, symbol, current.isoformat())
                payload = evaluate_index(symbol, bars, current, hours)
                quote, unavailable = None, None
                option_provider = os.getenv('INDEX_OPTION_PROVIDER', 'none')
                if payload['direction'] != 'SKIP' and option_provider == 'upstox':
                    source = None
                    try:
                        source = OptionSource()
                        quote = source.candidate(symbol, 'CE' if payload['direction'] == 'UP' else 'PE', payload['price'], clock().astimezone(IST))
                    except Exception as error:
                        unavailable = str(error) if isinstance(error,MarketError) else 'Option data could not be checked.'
                    finally:
                        if source: source.close()
                # Slow option requests cannot publish an already-expired index setup.
                current = clock()
                if payload['valid_until'] and current >= datetime.fromisoformat(payload['valid_until']):
                    payload.update(direction='SKIP', reason='The index setup expired while data was being checked.', valid_until=None)
                payload['data_cutoff'] = payload['assessed_at']
                payload['assessed_at'] = utcstamp(current.isoformat())
                payload['option'] = assess_option(payload['direction'], quote, current, unavailable=unavailable)
                payload['bars_added'] = added
                status = 'ok'
            except Exception as error:
                session.rollback()
                current = clock()
                detail = str(error) if isinstance(error,MarketError) else 'Index data could not be checked. Try again later.'
                payload = dict(symbol=symbol, name=INDICES[symbol]['name'], direction='SKIP', reason=detail,
                    assessed_at=utcstamp(current.isoformat()), candle_at=None, price=None, strategy=STRATEGY,
                    valid_until=None, mode='paper', validated=False, source=SOURCE, may_be_delayed=True,
                    option=assess_option('SKIP',None,current), candle_ids=[], bars_added=0)
                status = 'failed'
            save_assessment(session, payload)
            session.commit()  # One failed index never discards the other index's observations.
            results.append(dict(symbol=symbol,status=status,detail=payload['reason'],bars_added=payload['bars_added']))
    finally:
        if owns_provider: provider.close()
    return results


def display_assessment(row, current):
    payload = json.loads(row.payload)
    payload['id'] = row.id
    payload['saved_direction'] = payload['direction']
    payload['saved_option_action'] = payload['option']['action']
    expiry = payload.get('valid_until')
    if payload['direction'] != 'SKIP' and (not expiry or current >= datetime.fromisoformat(expiry)):
        payload.update(direction='SKIP', reason='The saved setup has expired. Fetch the latest check.', expired=True)
    option_expiry = payload['option'].get('valid_until')
    if payload['option']['action'] != 'SKIP' and (payload['direction'] == 'SKIP' or not option_expiry or current >= datetime.fromisoformat(option_expiry)):
        payload['option'].update(action='SKIP', reason='The saved option quote has expired. Fetch a fresh check.')
    return payload


def snapshot(session, current=None):
    current = current or clock()
    latest = []
    for symbol, info in INDICES.items():
        row = session.scalar(select(IndexAssessment).where(IndexAssessment.symbol == symbol).order_by(IndexAssessment.id.desc()).limit(1))
        latest.append(display_assessment(row,current) if row else dict(symbol=symbol,name=info['name'],direction='SKIP',
            reason='No index check saved yet. Fetch the latest candles.', assessed_at=None, candle_at=None, price=None,
            option=assess_option('SKIP',None,current), mode='paper', source=SOURCE))
    history = session.scalars(select(IndexAssessment).order_by(IndexAssessment.id.desc()).limit(20)).all()
    return dict(indices=latest, history=[dict(id=r.id,symbol=r.symbol,at=r.assessed_at,direction=r.direction,
        option_action=r.option_action,reason=json.loads(r.payload)['reason']) for r in history],
        strategy=STRATEGY,mode='paper',validated=False,refresh_seconds=300,limits=paper_limits(),
        option_provider=os.getenv('INDEX_OPTION_PROVIDER','none'), server_time=utcstamp(current.isoformat()),
        notice='Unvalidated price-only paper research. Yahoo candles may be delayed. No orders or option-profit claims.')
