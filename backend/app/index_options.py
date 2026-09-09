"""One-lot option paper assessment. Never a claim of a fill or validated profitability."""
import math
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from .market import IST


def paper_limits():
    try:
        capital = float(os.getenv('INDEX_PAPER_CAPITAL', '10000'))
        costs = float(os.getenv('INDEX_COST_BUFFER', '60'))
        if not math.isfinite(capital) or not 1000 <= capital <= 10000000 or not math.isfinite(costs) or not 0 < costs <= 10000:
            raise ValueError()
    except ValueError:
        return {'valid':False, 'capital':None, 'risk':None, 'costs':None}
    return {'valid':True, 'capital':capital, 'risk':round(capital * .01, 2), 'costs':costs}


def assess_option(direction, quote, current, limits=None, unavailable=None):
    limits = limits or paper_limits()
    result = dict(action='SKIP', reason='The index has no fresh entry setup.', contract=None, limits=limits,
                  valid_until=None, mode='paper', validated=False)
    if direction not in ('UP','DOWN'): return result
    result['reason'] = unavailable or 'Connect a permitted option feed for current contracts, lot sizes and bid/ask prices.'
    if quote is None: return result
    def skip(reason):
        result['reason'] = reason
        return result
    try:
        if any(not isinstance(quote.get(k), str) or not quote[k] for k in
               ('symbol','side','instrument','name','expiry','quote_at','received_at','source')):
            return skip('The option identity or timestamps are incomplete.')
        side = 'CE' if direction == 'UP' else 'PE'
        if quote['side'] != side or quote['contract_verified'] is not True or not quote['instrument'].startswith('NSE_FO|'):
            return skip('The option identity could not be verified.')
        expiry = date.fromisoformat(quote['expiry'])
        if not 0 < (expiry - current.astimezone(IST).date()).days <= 45: return skip('Skip expiry-day or expired contracts.')
        moment = datetime.fromisoformat(quote['quote_at']); receipt = datetime.fromisoformat(quote['received_at'])
        if moment.tzinfo is None or receipt.tzinfo is None: return skip('Option timestamps need a timezone.')
        if moment > receipt: return skip('The option quote is dated after its receipt time.')
        if not 0 <= (current - moment).total_seconds() <= 60 or not 0 <= (current - receipt).total_seconds() <= 60:
            return skip('Option prices are old or future-dated. A fresh quote is required.')
        numbers = [quote[k] for k in ('strike','bid','ask','tick','lot','volume','oi','bid_qty','ask_qty')]
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x <= 0 for x in numbers):
            return skip('Option price, trading activity or lot size is missing.')
        if quote['lot'] != int(quote['lot']) or quote['lot'] > 100000: return skip('The contract lot size is invalid.')
        # Save only validated fields. Raw NaN or arbitrary provider values must not
        # make a rejected quote impossible to store in the immutable JSON journal.
        result['contract'] = {key:quote[key] for key in ('symbol','side','instrument','name','expiry','strike',
            'lot','tick','bid','ask','bid_qty','ask_qty','volume','oi','quote_at','received_at','source')}
        bid, ask, lot, tick = (quote[k] for k in ('bid','ask','lot','tick'))
        if bid > ask or (ask - bid) / ask > .01: return skip('The buy/sell spread is crossed or wider than 1%.')
        if min(quote['bid_qty'], quote['ask_qty']) < lot: return skip('There is not enough visible quantity for one lot.')
        if not limits['valid']: return skip('The server paper-capital limits need correction.')
        step = Decimal(str(tick)); entry = Decimal(str(ask))
        # Deliberate, versioned research assumptions, not a calibrated optimum or exchange order.
        stop = (entry * Decimal('.8') / step).to_integral_value(rounding=ROUND_FLOOR) * step
        target = (entry * Decimal('1.4') / step).to_integral_value(rounding=ROUND_CEILING) * step
        if not 0 < stop < entry: return skip('The premium stop cannot be represented with this contract tick.')
        loss = round((ask - float(stop)) * lot + limits['costs'], 2)
        funding = round(ask * lot + limits['costs'], 2)
        gain = round((float(target) - ask) * lot - limits['costs'], 2)
        result.update(entry=ask, stop=float(stop), target=float(target), lot=lot, lots=1,
                      planned_loss=loss, premium_at_risk=funding, target_net=gain)
        if funding > limits['capital'] or loss > limits['risk']: return skip('One lot exceeds the cash or 1% planned-loss limit.')
        if gain < 1.5 * loss: return skip('The assumed target does not cover 1.5 times the planned loss after costs.')
        result.update(action='BUY_CALL' if side == 'CE' else 'BUY_PUT',
            reason='One-lot paper candidate: contract, freshness, spread and planned-loss checks passed.',
            valid_until=(min(moment, receipt) + timedelta(seconds=60)).isoformat(timespec='seconds'))
        return result
    except (KeyError, TypeError, ValueError, OverflowError):
        return skip('Option data was incomplete or invalid. No candidate was created.')
