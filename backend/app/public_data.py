"""Public Yahoo observations and a verified local NSE calendar. No broker key needed."""
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from .config import ROOT
from .market import IST, MarketError

INDEX_SYMBOLS = {'NIFTY50': '^NSEI', 'NIFTY': '^NSEI', 'NIFTY 50': '^NSEI',
    'BANKNIFTY': '^NSEBANK', 'NIFTYBANK': '^NSEBANK', 'NIFTY BANK': '^NSEBANK'}

def starter_universe(session):
    """Explicit small watchlist, verified against Yahoo on receipt; not index membership."""
    from .models import Instrument, Setting
    symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'ITC',
        'HINDUNILVR', 'LT', 'BHARTIARTL', 'AXISBANK', 'MARUTI', 'SUNPHARMA', 'NTPC',
        'POWERGRID', 'TITAN', 'ASIANPAINT', 'ULTRACEMCO', 'BAJFINANCE', 'HCLTECH']
    provider = YFinance()
    added = 0
    try:
        for symbol in symbols:
            if session.get(Instrument, symbol): continue
            _, meta = provider._history(symbol + '.NS', period='5d', interval='1d')
            name = meta.get('longName') or meta.get('shortName')
            if not name: raise MarketError('Yahoo did not identify a starter-watchlist company.')
            session.add(Instrument(symbol=symbol, name=name[:120], sector='Not classified', kind='stock',
                member_from=datetime.now(IST).date().isoformat()))
            added += 1
        saved = session.get(Setting, 'universe_description')
        description = '20-stock starter watchlist, observed today; not a complete Nifty 500 universe or historical index membership.'
        if saved: saved.value = description
        else: session.add(Setting(key='universe_description', value=description))
        session.flush()
    finally: provider.close()
    return {'added': added, 'universe': description}

def yahoo_symbol(instrument):
    if instrument.kind == 'index':
        if instrument.symbol not in INDEX_SYMBOLS:
            raise MarketError(f'{instrument.symbol}: no verified Yahoo index mapping is configured.')
        return INDEX_SYMBOLS[instrument.symbol]
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&.-]{0,29}', instrument.symbol):
        raise MarketError('Invalid NSE stock symbol in the supplied universe.')
    return instrument.symbol + '.NS'

class YFinance:
    id = 'yfinance'
    name = 'Yahoo Finance'
    refresh_seconds = 300
    batch_size = 1
    notice = 'Free Yahoo data may be delayed or unavailable. This is not an execution feed.'

    def __init__(self, ticker_factory=None, calendar_path=None):
        if ticker_factory is None:
            import yfinance as yf
            # yfinance otherwise writes cookies/timezone caches outside the project.
            yf.set_tz_cache_location(str(ROOT / 'data' / 'yfinance-cache'))
            ticker_factory = yf.Ticker
        self.ticker_factory = ticker_factory
        override = ROOT / 'data' / 'nse-holidays.json'
        self.calendar_path = Path(calendar_path) if calendar_path else override if override.exists() else ROOT / 'backend' / 'data' / 'nse-calendar-2026.json'

    def close(self):
        pass

    def timings(self, day):
        target = date.fromisoformat(day)
        try:
            calendar = json.loads(self.calendar_path.read_text())
            holidays = calendar[str(target.year)]
            if not isinstance(holidays, list) or any(date.fromisoformat(x).year != target.year for x in holidays):
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise MarketError(f'Load a verified data/nse-holidays.json for {target.year}; Yahoo does not verify NSE sessions.') from None
        # Explicit overrides handle special openings and unexpected closures.
        special = calendar.get('sessions', {}).get(day, 'regular')
        if special is None: return []
        if special == 'regular':
            if target.weekday() >= 5 or day in holidays: return []
            opening, closing = '09:15', '15:30'
        else:
            try: opening, closing = special['open'], special['close']
            except (TypeError, KeyError): raise MarketError('Invalid special-session calendar entry.') from None
        return [{'exchange': 'NSE', 'start_time': f'{day}T{opening}:00+05:30',
            'end_time': f'{day}T{closing}:00+05:30'}]

    def _history(self, key, **kwargs):
        try:
            ticker = self.ticker_factory(key)
            frame = ticker.history(auto_adjust=False, back_adjust=False, repair=False,
                actions=True, timeout=15, raise_errors=True, **kwargs)
            if frame is None or frame.empty:
                raise MarketError('Yahoo returned no price history. Existing observations are kept.')
            meta = ticker.get_history_metadata()
            if meta.get('currency') != 'INR' or meta.get('exchangeTimezoneName') != 'Asia/Kolkata' or meta.get('symbol') != key:
                raise MarketError('Yahoo symbol, currency or exchange timezone did not match the requested Indian instrument.')
            return frame, meta
        except MarketError: raise
        except Exception:
            # Errors may contain remote response bodies or account cookies.
            raise MarketError('Yahoo request failed or was limited. The worker will retry later.') from None

    def candles(self, key, start, end):
        date.fromisoformat(start)
        exclusive_end = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        frame, _ = self._history(key, start=start, end=exclusive_end, interval='1d')
        result = []
        for stamp, row in frame.iterrows():
            if stamp.tzinfo is None: raise MarketError('Yahoo candle timezone is missing.')
            prices = [float(row[k]) for k in ('Open', 'High', 'Low', 'Close')]
            if not all(math.isfinite(x) and x > 0 for x in prices): continue
            result.append([stamp.isoformat(), *prices, int(row['Volume'])])
        if not result: raise MarketError('Yahoo returned no valid daily candles.')
        # Preserve provider OHLC. Corporate-action reconciliation is a separate step;
        # never rewrite accepted bars using today's retrospectively adjusted values.
        return result

    def quotes(self, keys):
        result = {}
        for key in keys:
            frame, meta = self._history(key, period='5d', interval='1d')
            market_time = meta.get('regularMarketTime')
            price = meta.get('regularMarketPrice')
            if isinstance(market_time, datetime):
                if market_time.tzinfo is None: continue
                stamp = market_time.astimezone(timezone.utc)
            elif isinstance(market_time, (int, float)) and math.isfinite(market_time):
                stamp = datetime.fromtimestamp(market_time, timezone.utc)
            else: continue
            market_day = stamp.astimezone(IST).date()
            previous = frame[[x.date() < market_day for x in frame.index]]
            if previous.empty: continue
            baseline = float(previous.iloc[-1]['Close'])
            if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0: continue
            result[key] = {'instrument_token': key, 'last_price': price,
                'net_change': price - baseline, 'timestamp': stamp.isoformat(timespec='seconds')}
        return result

    def history_source(self, key, start, end):
        return f'https://finance.yahoo.com/quote/{quote(key, safe="")}/history/'
