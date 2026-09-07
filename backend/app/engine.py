"""Time-safe feature access, frozen forecasts and independently recorded outcomes."""
import json
import math
from datetime import datetime, timezone
from statistics import stdev
from sqlalchemy import select
from .models import Evidence, Instrument, Prediction, Price, Resolution

def utcstamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('A timestamp must include its timezone')
    return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')

def cutoff_for(day):
    return utcstamp(f'{day}T07:00:00+05:30')

def feature_prices(session, symbol, *, cutoff, limit=30):
    cutoff = utcstamp(cutoff)
    # Both filters are deliberate: a late-arriving old article/bar was not known earlier.
    query = select(Price).where(Price.symbol == symbol, Price.published_at <= cutoff,
                                Price.ingested_at <= cutoff).order_by(Price.date.desc()).limit(limit)
    return list(reversed(session.scalars(query).all()))

def feature_evidence(session, symbol, *, cutoff):
    cutoff = utcstamp(cutoff)
    return session.scalars(select(Evidence).where(Evidence.symbol == symbol,
        Evidence.published_at <= cutoff, Evidence.ingested_at <= cutoff).order_by(Evidence.published_at.desc()).limit(20)).all()

def paper_profit(direction, entry, exit, amount=1000.0, cost_rate=0.0015):
    if direction not in ('UP','DOWN') or not all(math.isfinite(v) for v in (entry,exit,amount,cost_rate)):
        raise ValueError('Invalid trade values')
    if entry <= 0 or exit <= 0 or amount <= 0 or not 0 <= cost_rate < 1:
        raise ValueError('Prices and amount must be positive; cost rate must be in [0,1)')
    change = (exit-entry)/entry
    return amount * (change if direction == 'UP' else -change) - amount*cost_rate

def split_adjust(prices, numerator, denominator):
    """Split 1 old share into numerator/denominator new shares; pure, raw rows retained."""
    if numerator <= 0 or denominator <= 0:
        raise ValueError('Split ratio must be positive')
    ratio = numerator/denominator
    return [{**p, **{k:p[k]/ratio for k in ('open','high','low','close')}, 'volume':p['volume']*ratio} for p in prices]

def capped_judge_probability(model_probability, proposed, event_impact=0):
    bound = 1 if abs(event_impact) == 2 else 0.15
    return max(0.01, min(0.99, max(model_probability-bound, min(model_probability+bound, proposed))))

def make_daily_calls(session, day, *, synthetic=False, model_name='momentum_research_v1', required_price_date=None):
    cutoff = cutoff_for(day)
    if session.scalar(select(Prediction.id).where(Prediction.date == day, Prediction.model_version == model_name).limit(1)):
        return 0
    instruments = session.scalars(select(Instrument).where(Instrument.member_from <= day)).all()
    candidates = []
    for instrument in instruments:
        if instrument.member_to and instrument.member_to < day:
            continue
        rows = feature_prices(session, instrument.symbol, cutoff=cutoff)
        if len(rows) < 6:
            continue
        if required_price_date and rows[-1].date != required_price_date:
            continue
        if not synthetic and any(p.synthetic for p in rows):
            raise ValueError('Sample prices cannot enter a live forecast')
        closes = [p.close for p in rows]
        changes = [(b-a)/a for a,b in zip(closes,closes[1:])]
        momentum = closes[-1]/closes[-6]-1
        volatility = max(stdev(changes) if len(changes)>1 else .01, .006)
        # Research rule, not a trained/calibrated ML model. Confidence explicitly unverified.
        probability = round(.5 + .17*math.tanh(momentum/(volatility*2.5)), 4)
        direction = 'UP' if probability >= .5 else 'DOWN'
        evidence = feature_evidence(session, instrument.symbol, cutoff=cutoff)
        source = [{'label':'Generated price history' if synthetic else 'Imported price history',
                   'url':None if synthetic else rows[-1].source, 'published_at':rows[-1].published_at,
                   'ingested_at':rows[-1].ingested_at}]
        source += [{'label':e.title,'url':e.url,'published_at':e.published_at,'ingested_at':e.ingested_at} for e in evidence[:2]]
        ref = closes[-1]
        row = dict(symbol=instrument.symbol,date=day,data_cutoff=cutoff,horizon='open_close',
            direction=direction,prob_up=probability,expected_low=round(ref*(1-1.4*volatility),2),
            expected_high=round(ref*(1+1.4*volatility),2),invalidation=round(ref*(1-volatility if direction=='UP' else 1+volatility),2),
            ref_price=round(ref,2),rationale=f'Price has {"risen" if momentum>=0 else "fallen"} {abs(momentum)*100:.1f}% over the last five sessions. This rule expects that direction to continue; a reversal would work against it.',
            sources=json.dumps(source),synthetic=synthetic)
        candidates.append((abs(probability-.5)*volatility,row))
    picked = []
    for direction in ('UP','DOWN'):
        rows = sorted((x for x in candidates if x[1]['direction']==direction), key=lambda x:x[0], reverse=True)[:5]
        if len(rows) != 5:
            raise ValueError(f'Need five supported {direction} calls; found {len(rows)}. No directions were fabricated.')
        for rank,(_,row) in enumerate(rows,1):
            row['rank']=rank
            picked.append(row['symbol'])
    for _,row in candidates:
        session.add(Prediction(**row,model_version=model_name))
        for baseline in ('baseline_always_up','baseline_momentum_5d'):
            base = {**row}
            if baseline == 'baseline_always_up':
                base.update(direction='UP',prob_up=.53,rationale='Fixed reference: always predict up with 53% probability. This is a benchmark setting, not a verified market statistic.')
            session.add(Prediction(**base,model_version=baseline))
    session.flush()
    return len(picked)

def resolve_day(session, day):
    count = 0
    rows = session.scalars(select(Prediction).where(Prediction.date==day)).all()
    for p in rows:
        if session.get(Resolution,p.id):
            continue
        bar = session.scalar(select(Price).where(Price.symbol==p.symbol,Price.date==day))
        if not bar:
            continue  # Pending stays pending if the day's file is late.
        if bar.synthetic != p.synthetic:
            raise ValueError('Sample and live outcomes cannot be mixed')
        entry = bar.open if p.horizon=='open_close' else p.ref_price
        movement = bar.close-entry
        right = None if movement==0 else ((movement>0)==(p.direction=='UP'))
        instrument = session.get(Instrument,p.symbol)
        traded = instrument.kind=='stock'
        pnl = paper_profit(p.direction,entry,bar.close,p.allocation,p.cost_rate) if traded else None
        baseline = paper_profit('UP',entry,bar.close,p.allocation,p.cost_rate) if traded else None
        session.add(Resolution(prediction_id=p.id,entry=entry,exit=bar.close,right=right,pnl=pnl,
            baseline_pnl=baseline,costs=p.allocation*p.cost_rate if traded else 0,
            cause='MODEL_NOISE' if right is False else None,
            explanation='The closing move went against the call. No verified event establishes why; the cause remains uncertain.' if right is False else None,
            resolved_at=utcstamp(f'{day}T18:30:00+05:30') if p.synthetic else datetime.now(timezone.utc).isoformat(timespec='seconds')))
        count+=1
    session.flush()
    return count

def can_promote(champion, challenger):
    """Matched, genuinely out-of-sample predictions; never score fitted training outputs."""
    left={x['key']:x for x in champion}
    right={x['key']:x for x in challenger}
    keys=set(left)&set(right)
    if len({left[k]['date'] for k in keys})<60 or not keys:
        return False
    if any(not right[k].get('out_of_sample') or left[k]['outcome']!=right[k]['outcome'] for k in keys):
        return False
    error=lambda rows:sum((rows[k]['prob_up']-rows[k]['outcome'])**2 for k in keys)/len(keys)
    return error(right)<error(left)
