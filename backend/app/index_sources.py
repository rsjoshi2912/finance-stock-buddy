"""Index-only data adapters. No cash-universe edits, scraping bypasses or order endpoints."""
from datetime import date, datetime, timezone
import math

from .market import IST, MarketError, Upstox, timestamp
from .public_data import YFinance

INDICES = {'NIFTY': {'name':'Nifty 50', 'yahoo':'^NSEI', 'upstox':'NSE_INDEX|Nifty 50'},
           'BANKNIFTY': {'name':'Bank Nifty', 'yahoo':'^NSEBANK', 'upstox':'NSE_INDEX|Nifty Bank'}}


def index_candles(provider, symbol):
    """Receipt time is assigned by the caller after this entire request returns."""
    frame, _ = provider._history(INDICES[symbol]['yahoo'], period='5d', interval='5m')
    rows = []
    if len(frame) > 2500: raise MarketError('Index source returned too many candles.')
    for stamp, row in frame.iterrows():
        if stamp.tzinfo is None: raise MarketError('Index candle timezone is missing.')
        values = [float(row[key]) for key in ('Open', 'High', 'Low', 'Close')]
        if not all(math.isfinite(x) and x > 0 for x in values):
            raise MarketError('Index source returned an invalid price.')
        rows.append(dict(start_at=stamp.isoformat(), open=values[0], high=values[1], low=values[2], close=values[3]))
    return rows


class OptionSource:
    """Optional existing Upstox connection; contract master plus timestamped full quote."""
    def __init__(self, client=None):
        self.client = client or Upstox()

    def close(self): self.client.close()

    def candidate(self, symbol, side, spot, current):
        key = INDICES[symbol]['upstox']
        rows = self.client.get('/v2/option/contract', {'instrument_key':key})
        if not isinstance(rows, list) or len(rows) > 20000: raise MarketError('Option contracts were unavailable.')
        day = current.astimezone(IST).date()
        eligible = []
        for row in rows:
            try:
                expiry = date.fromisoformat(row['expiry'])
                strike = float(row['strike_price'])
                if (row['underlying_key'] != key or row['instrument_type'] != side or row['exchange'] != 'NSE'
                    or row['segment'] != 'NSE_FO' or row['underlying_type'] != 'INDEX'
                    or not 0 < (expiry - day).days <= 45 or not math.isfinite(strike) or strike <= 0): continue
                eligible.append(row)
            except (KeyError, TypeError, ValueError): continue
        if not eligible: raise MarketError('No verified, unexpired index option contract was returned.')
        # Choose the nearest non-expiry session contract and closest strike, not the cheapest premium.
        contract = min(eligible, key=lambda r: (r['expiry'], abs(float(r['strike_price']) - spot), float(r['strike_price'])))
        instrument = contract['instrument_key']
        quotes = self.client.quotes([instrument])
        quote = next((q for q in quotes.values() if q.get('instrument_token') == instrument), None)
        if not quote: raise MarketError('The option quote did not match its contract.')
        try:
            bid, ask = quote['depth']['buy'][0], quote['depth']['sell'][0]
            return dict(symbol=symbol, side=side, instrument=instrument, name=contract['trading_symbol'],
                expiry=contract['expiry'], strike=float(contract['strike_price']), lot=contract['lot_size'],
                tick=float(contract['tick_size']) / 100, bid=float(bid['price']), ask=float(ask['price']),
                bid_qty=bid['quantity'], ask_qty=ask['quantity'], volume=quote['volume'], oi=quote['oi'],
                quote_at=timestamp(quote['timestamp']), received_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                source='Upstox', contract_verified=True)
        except (KeyError, IndexError, TypeError, ValueError):
            raise MarketError('Option quote, depth or contract details were incomplete.') from None
