"""Daily call availability and notification state, separate from frozen forecasts."""
import json
from datetime import datetime, timezone
from sqlalchemy import func, select
from .engine import cutoff_for
from .market import IST
from .models import Prediction, ScheduledRun, Setting


def record_shortfall(session, day, error, current=None):
    current = current or datetime.now(timezone.utc)
    value = dict(status='skipped', reason=str(error), available_buy=error.buy, available_sell=error.sell,
                 cutoff=cutoff_for(day), recorded_at=current.astimezone(timezone.utc).isoformat(timespec='seconds'))
    key = f'daily_calls:{day}'
    row = session.get(Setting, key)
    if row: row.value = json.dumps(value)
    else: session.add(Setting(key=key, value=json.dumps(value)))
    session.flush()


def call_status(session, day, current=None):
    current = current or datetime.now(timezone.utc)
    count = session.scalar(select(func.count(Prediction.id)).where(Prediction.date == day,
        Prediction.rank.is_not(None), ~Prediction.model_version.startswith('baseline_'), Prediction.synthetic.is_(False))) or 0
    saved = session.get(Setting, f'daily_calls:{day}')
    job = session.get(ScheduledRun, f'predict:{day}')
    if count:
        result = dict(status='ready', reason=f'{count} morning call{"s" if count != 1 else ""} saved.')
    elif saved:
        result = json.loads(saved.value)
    elif job and job.status == 'failed':
        result = dict(status='skipped', reason='The morning checks failed. No calls were saved. See System health.')
    elif day == current.astimezone(IST).date().isoformat() and current.astimezone(IST).strftime('%H:%M') < '08:25':
        result = dict(status='waiting', reason='Morning checks run 07:20–08:25 IST on trading days.')
    else:
        result = dict(status='skipped', reason='No morning calls were saved for this date.')
    delivery = session.get(Setting, f'telegram:morning:{day}')
    return dict(result, day=day, saved_calls=count,
                telegram='sent' if delivery and delivery.value == 'sent' else 'unconfirmed' if delivery else 'not_attempted')
