"""Owner-triggered background fetch. Never predicts, resolves trades or sends messages."""
import json
import math
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from .config import MODE
from .db import SessionLocal
from .fetch_lock import source_lock
from .market import MarketError, create_provider, refresh_quotes
from .models import JobRun, Setting
from .news import collect_news

KEY = 'manual_latest_fetch'
COOLDOWN_SECONDS = 60
MAX_RUN_SECONDS = 600
BUSY = ('queued', 'running')

class RefreshCooldown(ValueError):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(f'Please wait {seconds} seconds before fetching again.')

def current_time(): return datetime.now(timezone.utc)

def public_state(value, current=None):
    current = current or current_time()
    state = dict(value or {'id': None, 'status': 'idle', 'message': 'Fetch the latest available prices and news.'})
    if state['status'] in BUSY and (current - datetime.fromisoformat(state['updated_at'])).total_seconds() > MAX_RUN_SECONDS:
        state.update(status='interrupted', message='The previous fetch stopped responding. You can try again.')
    state['busy'] = state['status'] in BUSY
    finished = state.get('completed_at')
    state['retry_after_seconds'] = max(0, math.ceil(COOLDOWN_SECONDS - (current - datetime.fromisoformat(finished)).total_seconds())) if finished else 0
    return state

def refresh_status(session, current=None):
    row = session.get(Setting, KEY)
    return public_state(json.loads(row.value) if row else None, current)

def request_refresh(session, current=None):
    current = current or current_time()
    mode = session.get(Setting, 'dataset_mode')
    if MODE != 'live' or not os.getenv('OWNER_PASSWORD') or not mode or mode.value != 'live':
        raise MarketError('Fetch latest is available in the configured live-data workspace.')
    for _ in range(3):
        row = session.get(Setting, KEY, populate_existing=True)
        raw = row.value if row else None
        state = public_state(json.loads(raw) if raw else None, current)
        if state['busy']: return state, False
        if state['retry_after_seconds']: raise RefreshCooldown(state['retry_after_seconds'])
        stamp = current.isoformat(timespec='seconds')
        value = dict(id=uuid.uuid4().hex, status='queued', requested_at=stamp, updated_at=stamp,
            completed_at=None, stage='queued', message='Starting the fetch…', prices=None, news=None)
        encoded = json.dumps(value)
        if row:
            claimed = session.execute(update(Setting).where(Setting.key == KEY, Setting.value == raw).values(value=encoded)).rowcount == 1
            if claimed: session.commit(); return public_state(value, current), True
            session.rollback()
        else:
            session.add(Setting(key=KEY, value=encoded))
            try: session.commit(); return public_state(value, current), True
            except IntegrityError: session.rollback()
    raise MarketError('Another request changed the fetch state. Check the current progress.')

def save_progress(factory, request_id, **changes):
    with factory() as session:
        row = session.get(Setting, KEY)
        if not row: return False
        raw = row.value; value = json.loads(raw)
        if value['id'] != request_id: return False
        value.update(changes, updated_at=current_time().isoformat(timespec='seconds'))
        changed = session.execute(update(Setting).where(Setting.key == KEY, Setting.value == raw).values(value=json.dumps(value))).rowcount == 1
        session.commit()
        return changed

def safe_error(error):
    return str(error) if isinstance(error, MarketError) else 'The fetch failed. Check System health and try again.'

def run_refresh(request_id, factory=SessionLocal):
    if not save_progress(factory, request_id, status='running', stage='prices', message='Fetching prices…'): return
    prices, news = None, None
    try:
        with factory() as session:
            bind = session.get_bind()
        with source_lock(bind):
            provider = None
            try:
                provider = create_provider()
                with factory() as session:
                    count = refresh_quotes(session, provider)
                    session.commit()
                prices = dict(status='ok', count=count, detail=f'Checked {count} prices. Their market timestamps are shown below.')
            except Exception as error:
                prices = dict(status='failed', count=0, detail=safe_error(error))
            finally:
                if provider: provider.close()
            save_progress(factory, request_id, prices=prices, stage='news', message='Fetching news…')
            try:
                if os.getenv('NEWS_ENABLED', 'true') != 'true':
                    news = dict(status='skipped', count=0, detail='News collection is switched off.')
                else:
                    with factory() as session:
                        sources = collect_news(session)
                        session.commit()
                    added = sum(x['added'] for x in sources)
                    good = sum(x['status'] == 'ok' for x in sources)
                    status = 'ok' if sources and good == len(sources) else 'partial' if good else 'failed'
                    news = dict(status=status, count=added, sources=sources,
                        detail=f'Added {added} articles. {good} of {len(sources)} feeds returned recent news.' if sources else 'No news feeds are selected.')
            except Exception as error:
                news = dict(status='failed', count=0, detail=safe_error(error))
        complete = prices['status'] == 'ok' and news['status'] in ('ok', 'skipped')
        usable = prices['status'] == 'ok' or news['status'] in ('ok', 'partial')
        status = 'complete' if complete else 'partial' if usable else 'failed'
        message = 'Fetch complete.' if complete else 'Some sources need attention. Available updates are saved.' if usable else 'The fetch could not finish. Previous data is kept.'
    except Exception as error:
        status, message = 'failed', safe_error(error)
    finished = current_time().isoformat(timespec='seconds')
    if save_progress(factory, request_id, status=status, stage='finished', message=message,
        prices=prices, news=news, completed_at=finished):
        with factory() as session:
            session.add(JobRun(job='manual refresh', status='ok' if status == 'complete' else 'warning' if status == 'partial' else 'failed',
                rows=(prices or {}).get('count', 0) + (news or {}).get('count', 0), detail=message, started_at=finished))
            session.commit()
