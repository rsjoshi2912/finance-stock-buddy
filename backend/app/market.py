"""Read-only provider boundary. Observations always retain their source and time."""
import csv
import io
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo
from types import SimpleNamespace

import httpx
from sqlalchemy import select

from .engine import utcstamp
from .ingest import import_prices, now
from .models import Instrument, InstrumentMapping, Price, Quote, Setting

IST = ZoneInfo('Asia/Kolkata')
BASE = 'https://api.upstox.com'

class MarketError(ValueError):
    pass

class Upstox:
    id = 'upstox'
    name = 'Upstox'
    refresh_seconds = 15
    batch_size = 500
    notice = 'Broker quote snapshots. Check each price timestamp.'

    def __init__(self, token=None, transport=None):
        self.token = token or os.getenv('UPSTOX_ACCESS_TOKEN')
        if not self.token:
            raise MarketError('Set UPSTOX_ACCESS_TOKEN on the backend server.')
        self.client = httpx.Client(timeout=25, transport=transport, follow_redirects=False)

    def close(self):
        self.client.close()

    def get(self, path, params=None):
        # This client intentionally has no order or account endpoints.
        if path != '/v2/option/contract' and not path.startswith(('/v2/market/', '/v2/market-quote/', '/v3/historical-candle/')):
            raise MarketError('Only market-data endpoints are allowed.')
        try:
            response = self.client.get(BASE + path, params=params,
                headers={'Authorization': f'Bearer {self.token}', 'Accept': 'application/json'})
            if response.status_code in (401, 403):
                raise MarketError('Market-data access was rejected. Check or renew the server token.')
            if response.status_code == 429:
                raise MarketError('Market-data request limit reached. The worker will retry later.')
            if response.status_code != 200:
                raise MarketError(f'Market-data service returned HTTP {response.status_code}.')
            result = response.json()
            if result.get('status') != 'success' or 'data' not in result:
                raise MarketError('Market-data response was incomplete.')
            return result['data']
        except (httpx.HTTPError, json.JSONDecodeError):
            raise MarketError('Market-data request failed. Previous observations are kept.') from None

    def timings(self, day):
        date.fromisoformat(day)
        return self.get(f'/v2/market/timings/{day}')

    def candles(self, key, start, end):
        date.fromisoformat(start); date.fromisoformat(end)
        return self.get(f'/v3/historical-candle/{quote(key, safe="")}/days/1/{end}/{start}')['candles']

    def quotes(self, keys):
        return self.get('/v2/market-quote/quotes', {'instrument_key': ','.join(keys)})

    def history_source(self, key, start, end):
        return f'{BASE}/v3/historical-candle/{quote(key, safe="")}/days/1/{end}/{start}'

def provider_id():
    name = os.getenv('MARKET_DATA_PROVIDER', 'yfinance').lower()
    if name not in ('yfinance', 'upstox'):
        raise MarketError('MARKET_DATA_PROVIDER must be yfinance or upstox.')
    return name

def create_provider():
    if provider_id() == 'upstox': return Upstox()
    from .public_data import YFinance
    return YFinance()

def timestamp(value):
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(float(value) / 1000, timezone.utc).isoformat(timespec='seconds')
    return utcstamp(value)

def market_session(session, provider, day, refresh=False):
    key = f'market-session:{day}'
    saved = session.get(Setting, key)
    current = datetime.now(timezone.utc)
    if saved and not refresh:
        stored = json.loads(saved.value)
        if stored.get('provider') == getattr(provider, 'id', 'upstox') and (current - datetime.fromisoformat(stored['checked_at'])).total_seconds() < 21600:
            return stored
    rows = provider.timings(day)
    if not isinstance(rows, list):
        raise MarketError('The exchange schedule was not available.')
    nse = [x for x in rows if x.get('exchange') == 'NSE']
    result = {'date': day, 'open': None, 'close': None, 'checked_at': now(), 'provider': getattr(provider, 'id', 'upstox')}
    if nse:
        result.update(open=timestamp(nse[0]['start_time']), close=timestamp(nse[0]['end_time']))
        if result['open'] >= result['close'] or datetime.fromisoformat(result['open']).astimezone(IST).date().isoformat() != day:
            raise MarketError('The exchange session times are inconsistent.')
    if saved: saved.value = json.dumps(result)
    else: session.add(Setting(key=key, value=json.dumps(result)))
    session.flush()
    return result

def previous_session(session, provider, day):
    for offset in range(1, 15):
        candidate = (date.fromisoformat(day) - timedelta(days=offset)).isoformat()
        if market_session(session, provider, candidate)['open']:
            return candidate
    raise MarketError('Could not establish the previous NSE session.')

def mappings(session, day=None, provider='upstox'):
    if provider == 'yfinance':
        from .public_data import yahoo_symbol
        query = select(Instrument)
        if day:
            query = query.where(Instrument.member_from <= day,
                (Instrument.member_to.is_(None)) | (Instrument.member_to >= day))
        result = [SimpleNamespace(symbol=i.symbol, instrument_key=yahoo_symbol(i))
            for i in session.scalars(query.order_by(Instrument.symbol))]
        if not result: raise MarketError('Import a verified universe CSV before fetching prices.')
        return result
    query = select(InstrumentMapping).join(Instrument).where(InstrumentMapping.provider == 'upstox')
    if day:
        query = query.where(Instrument.member_from <= day,
            (Instrument.member_to.is_(None)) | (Instrument.member_to >= day))
    values = session.scalars(query.order_by(InstrumentMapping.symbol)).all()
    if not values:
        raise MarketError('Import a universe CSV with Upstox instrument_key values first.')
    return values

def import_mapping(session, content):
    from .ingest import import_instruments
    count = import_instruments(session, content)
    for row in csv.DictReader(io.StringIO(content)):
        symbol = row['symbol'].strip().upper()
        key = row.get('instrument_key', '').strip()
        if not key.startswith(('NSE_EQ|', 'NSE_INDEX|')) or len(key) > 100:
            raise MarketError(f'{symbol}: supply the verified NSE instrument_key from Upstox.')
        existing = session.get(InstrumentMapping, symbol)
        if existing and existing.instrument_key != key:
            raise MarketError(f'{symbol}: instrument mapping changed; review it before replacing history.')
        if not existing:
            session.add(InstrumentMapping(symbol=symbol, instrument_key=key, provider='upstox'))
    session.flush()
    return count

def ingest_daily(session, provider, end, lookback=90, observed_at=None):
    received = utcstamp(observed_at or now())
    observed = datetime.fromisoformat(received).astimezone(IST)
    if date.fromisoformat(end) > observed.date() or (end == observed.date().isoformat() and (observed.hour, observed.minute) < (18, 30)):
        raise MarketError('Today’s daily candle is not accepted before 18:30 IST.')
    counts = {'accepted': 0, 'quarantined': 0, 'duplicate': 0, 'missing': 0}
    for item in mappings(session, observed.date().isoformat(), getattr(provider, 'id', 'upstox')):
        latest = session.scalar(select(Price).where(Price.symbol == item.symbol).order_by(Price.date.desc()).limit(1))
        # Fetch overlapping dates for a retry; the importer preserves original accepted bars.
        start = latest.date if latest else (date.fromisoformat(end) - timedelta(days=lookback)).isoformat()
        if start > end:
            continue
        candles = provider.candles(item.instrument_key, start, end)
        received = utcstamp(observed_at or now())
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'published_at'])
        found = False
        for bar in sorted(candles, key=lambda x: x[0]):
            day = datetime.fromisoformat(bar[0]).astimezone(IST).date().isoformat()
            if not start <= day <= end:
                continue
            found = found or day == end
            # Provider reports candle START, not publication time. Conservatively record
            # our receipt as first-known publication; never fabricate historical knowledge.
            writer.writerow([item.symbol, day, *bar[1:6], received])
        source = provider.history_source(item.instrument_key, start, end) if hasattr(provider, 'history_source') else Upstox.history_source(provider, item.instrument_key, start, end)
        result = import_prices(session, output.getvalue(), source, received)
        for key in result: counts[key] += result[key]
        if not found: counts['missing'] += 1
    return counts

def refresh_quotes(session, provider, observed_at=None):
    received = utcstamp(observed_at or now())
    day = datetime.fromisoformat(received).astimezone(IST).date().isoformat()
    entries = mappings(session, day, getattr(provider, 'id', 'upstox'))
    # Free sources are polled only for today's picks, or a small initial watchlist.
    if getattr(provider, 'id', 'upstox') == 'yfinance':
        from .models import Prediction
        picks = set(session.scalars(select(Prediction.symbol).where(Prediction.date == day, Prediction.rank.is_not(None))))
        entries = [x for x in entries if x.symbol in picks] if picks else entries[:10]
    updated = 0
    batch_size = getattr(provider, 'batch_size', 500)
    for offset in range(0, len(entries), batch_size):
        batch = entries[offset:offset + batch_size]
        payload = provider.quotes([x.instrument_key for x in batch])
        received = utcstamp(observed_at or now())
        by_key = {x.get('instrument_token'): x for x in payload.values()}
        for item in batch:
            row = by_key.get(item.instrument_key)
            if not row:
                continue
            try:
                price, change = float(row['last_price']), float(row['net_change'])
                market_at = timestamp(row.get('last_trade_time') or row['timestamp'])
                if not math.isfinite(price) or price <= 0 or not math.isfinite(change) or market_at > received:
                    continue
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            existing = session.get(Quote, item.symbol)
            if existing and market_at < existing.market_at:
                continue
            values = dict(price=price, change=change, market_at=market_at, received_at=received, provider=getattr(provider, 'name', 'Upstox'))
            if existing:
                for key, value in values.items(): setattr(existing, key, value)
            else:
                session.add(Quote(symbol=item.symbol, **values))
            updated += 1
    if not updated:
        raise MarketError('No valid price updates were returned. Previous timestamps are kept.')
    return updated

def quote_snapshot(session):
    current = datetime.now(timezone.utc)
    day = current.astimezone(IST).date().isoformat()
    saved = session.get(Setting, f'market-session:{day}')
    hours = json.loads(saved.value) if saved else None
    fresh_hours = hours and (current - datetime.fromisoformat(hours['checked_at'])).total_seconds() < 21600
    market_open = bool(fresh_hours and hours['open'] and hours['open'] <= current.isoformat() < hours['close'])
    quotes = []
    for q in session.scalars(select(Quote).order_by(Quote.symbol)):
        age = max(0, int((current - datetime.fromisoformat(q.market_at)).total_seconds()))
        receipt_age = max(0, int((current - datetime.fromisoformat(q.received_at)).total_seconds()))
        quotes.append(dict(symbol=q.symbol, price=q.price, change=q.change, market_at=q.market_at,
            received_at=q.received_at, age_seconds=age, stale=age > (1200 if q.provider == 'Yahoo Finance' else 90) or receipt_age > (600 if q.provider == 'Yahoo Finance' else 90),
            provider=q.provider, possibly_delayed=q.provider == 'Yahoo Finance'))
    heartbeat = session.get(Setting, 'worker_heartbeat')
    return dict(quotes=quotes, market_open=market_open, schedule_known=bool(fresh_hours),
        provider='Yahoo Finance' if provider_id() == 'yfinance' else 'Upstox', connected=bool(quotes),
        refresh_seconds=300 if provider_id() == 'yfinance' else 15,
        notice='Free Yahoo data may be delayed or unavailable. This is not an execution feed.' if provider_id() == 'yfinance' else Upstox.notice,
        worker_at=heartbeat.value if heartbeat else None, checked_at=current.isoformat(timespec='seconds'))
