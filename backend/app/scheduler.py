"""One persistent worker, exchange-verified sessions, bounded retries and durable jobs."""
import argparse
import fcntl
import json
import os
import signal
import time
from contextlib import contextmanager
from datetime import datetime, time as clock_time, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from .analytics import dashboard
from .briefs import evening, morning
from .config import MODE, ROOT
from .db import SessionLocal, engine, initialize
from .engine import cutoff_for, make_daily_calls, resolve_day
from .ingest import now
from .jobs import send_telegram
from .market import IST, MarketError, create_provider, ingest_daily, market_session, previous_session, refresh_quotes
from .news import collect_news
from .events import assess_new_articles, calendar_hours, record_outcomes
from .fetch_lock import source_lock
from .models import JobRun, Prediction, Resolution, ScheduledRun, Setting

def due_jobs(current, hours):
    """No catch-up of missed morning calls or messages after their useful window."""
    local = current.astimezone(IST)
    if not hours.get('open') or hours['date'] != local.date().isoformat():
        return []
    opened = datetime.fromisoformat(hours['open']).astimezone(IST)
    closed = datetime.fromisoformat(hours['close']).astimezone(IST)
    regular = opened.time() == clock_time(9, 15) and closed.time() == clock_time(15, 30)
    minute = local.hour * 60 + local.minute
    jobs = []
    if regular:
        if 360 <= minute < 415: jobs.append('history')
        if 440 <= minute < 505: jobs.append('predict')
        if 510 <= minute < 525: jobs.append('morning')
    if opened <= local <= closed:
        jobs.append('quotes')
    if regular and 1110 <= minute <= 1170:
        jobs.append('close')
    if regular and 1140 <= minute < 1155:
        jobs.append('evening')
    return jobs

def execute_once(factory, key, task, current=None):
    current = current or datetime.now(timezone.utc)
    stamp = current.isoformat(timespec='seconds')
    with factory() as session:
        record = session.get(ScheduledRun, key)
        if record:
            age = (current - datetime.fromisoformat(record.updated_at)).total_seconds()
            if record.status == 'ok' or record.attempts >= 3 or age < 60:
                return False
            record.status = 'running'; record.attempts += 1; record.updated_at = stamp
        else:
            session.add(ScheduledRun(key=key, status='running', attempts=1, updated_at=stamp))
        try: session.commit()
        except IntegrityError:
            session.rollback(); return False
    try:
        with factory() as session:
            if key.split(':')[0] in ('history', 'quotes', 'close', 'news'):
                with source_lock(session.get_bind()):
                    result = task(session)
                    session.commit()
            else:
                result = task(session)
                session.commit()
        status, detail = 'ok', str(result)[:500]
    except Exception as error:
        # HTTP exceptions can include URLs and credentials. Store only controlled messages.
        status = 'failed'
        detail = str(error)[:500] if isinstance(error, MarketError) else f'{type(error).__name__}: job failed; inspect server configuration'
    with factory() as session:
        record = session.get(ScheduledRun, key)
        record.status = status; record.detail = detail; record.updated_at = stamp
        if not key.startswith('quotes:') or status != 'ok':
            session.add(JobRun(job=key.split(':')[0], status=status, rows=0, detail=detail, started_at=stamp))
        session.commit()
    return status == 'ok'

def require_live(session):
    if MODE != 'live': raise MarketError('The scheduler requires APP_MODE=live and a separate database.')
    if not os.getenv('OWNER_PASSWORD'): raise MarketError('Set OWNER_PASSWORD before starting the live worker.')
    mode = session.get(Setting, 'dataset_mode')
    if mode and mode.value != 'live': raise MarketError('Refusing to run live jobs on the sample database.')
    if not mode: session.add(Setting(key='dataset_mode', value='live'))

def predict(session, provider, day, current):
    local = current.astimezone(IST)
    if day != local.date().isoformat() or not clock_time(7, 20) <= local.time() < clock_time(8, 25):
        raise MarketError('The morning prediction window has passed.')
    previous = previous_session(session, provider, day)
    return make_daily_calls(session, day, required_price_date=previous)

def deliver(session, day, period):
    data = dashboard(session, day)
    if data['mode'] != 'live' or len(data['calls']) != 10:
        raise MarketError('Ten saved live calls are required before a daily message can be sent.')
    message = (morning if period == 'morning' else evening)(data)
    send_telegram(message, period, day, session)
    return f'{period} note sent to the configured owner'

def news_job(session, provider):
    sources = collect_news(session)
    # Assessments are written as soon as an article is collected, before any reaction is known.
    assessed = assess_new_articles(session, hours=calendar_hours(session, provider))
    return {'sources': sources, 'assessed': assessed}

def load_history(session, provider, day):
    counts = ingest_daily(session, provider, previous_session(session, provider, day))
    return {'prices': counts, 'event_outcomes': record_outcomes(session, hours=calendar_hours(session, provider))}

def close_day(session, provider, day):
    counts = ingest_daily(session, provider, day)
    resolved = resolve_day(session, day)
    # Retry unresolved earlier calls too; their actual resolution time remains today.
    pending = session.scalars(select(Prediction.date).outerjoin(Resolution,
        Resolution.prediction_id == Prediction.id).where(Resolution.prediction_id.is_(None),
        Prediction.date < day).distinct()).all()
    for previous in pending: resolved += resolve_day(session, previous)
    outcomes = record_outcomes(session, hours=calendar_hours(session, provider))
    return {'prices': counts, 'resolved': resolved, 'event_outcomes': outcomes}

def tick(provider, current=None, factory=SessionLocal):
    current = current or datetime.now(timezone.utc)
    day = current.astimezone(IST).date().isoformat()
    with factory() as session:
        require_live(session)
        heartbeat = session.get(Setting, 'worker_heartbeat')
        stamp = current.isoformat(timespec='seconds')
        if heartbeat: heartbeat.value = stamp
        else: session.add(Setting(key='worker_heartbeat', value=stamp))
        session.commit()
        try:
            hours = market_session(session, provider, day)
        except MarketError as error:
            # News and display snapshots can still be collected without claiming that
            # exchange hours were confirmed. Forecasting/delivery stay blocked.
            hours = {'date': day, 'open': None, 'close': None}
            saved = session.get(Setting, 'calendar_warning')
            previous = json.loads(saved.value) if saved else None
            if not previous or (current - datetime.fromisoformat(previous['at'])).total_seconds() >= 1800:
                value = json.dumps({'at': stamp, 'detail': str(error)})
                if saved: saved.value = value
                else: session.add(Setting(key='calendar_warning', value=value))
                session.add(JobRun(job='calendar', status='warning', rows=0, detail=str(error), started_at=stamp))
        # High-frequency quote checks do not need permanent job-history rows.
        expired = (current - timedelta(days=7)).isoformat(timespec='seconds')
        session.execute(delete(ScheduledRun).where(ScheduledRun.key.startswith('quotes:'), ScheduledRun.updated_at < expired))
        session.execute(delete(JobRun).where(JobRun.job == 'quotes', JobRun.started_at < expired))
        session.commit()
    jobs = due_jobs(current, hours)
    local = current.astimezone(IST)
    if os.getenv('NEWS_ENABLED', 'true') == 'true' and 6 <= local.hour < 20: jobs.append('news')
    if not hours.get('open') and getattr(provider, 'id', '') == 'yfinance' and local.weekday() < 5 and 9 <= local.hour < 16:
        jobs.append('quotes')
    for job in jobs:
        suffix = day
        if job == 'quotes': suffix = str(int(current.timestamp() // getattr(provider, 'refresh_seconds', 15)))
        if job == 'news': suffix = str(int(current.timestamp() // 300))
        if job == 'close': suffix = f'{day}:{current.astimezone(IST).minute // 15}:{current.astimezone(IST).hour}'
        actions = {
            'history': lambda s: load_history(s, provider, day),
            'predict': lambda s: predict(s, provider, day, current),
            'quotes': lambda s: refresh_quotes(s, provider),
            'close': lambda s: close_day(s, provider, day),
            'morning': lambda s: deliver(s, day, 'morning'),
            'evening': lambda s: deliver(s, day, 'evening'),
            'news': lambda s: news_job(s, provider),
        }
        execute_once(factory, f'{job}:{suffix}', actions[job], current)
    return jobs

@contextmanager
def worker_lock():
    if engine.dialect.name == 'postgresql':
        with engine.connect() as connection:
            if not connection.scalar(text('SELECT pg_try_advisory_lock(7236919)')):
                raise MarketError('Another scheduler already owns this database.')
            try: yield
            finally: connection.execute(text('SELECT pg_advisory_unlock(7236919)'))
    else:
        with (ROOT / 'data' / 'scheduler.lock').open('a') as file:
            try: fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise MarketError('Another scheduler is already running.') from None
            yield

def main():
    parser = argparse.ArgumentParser(description='Run the Nifty Signal live worker')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args(); initialize()
    stop = False
    def shutdown(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, shutdown); signal.signal(signal.SIGINT, shutdown)
    provider = create_provider()
    try:
        with worker_lock():
            while not stop:
                try: tick(provider)
                except Exception as error:
                    detail=str(error) if isinstance(error, MarketError) else f'{type(error).__name__}: worker tick failed'
                    print(detail, flush=True)
                    try:
                        with SessionLocal() as session:
                            session.add(JobRun(job='worker',status='failed',rows=0,detail=detail,started_at=now()))
                            session.commit()
                    except Exception: pass  # The database may itself be unavailable.
                    if args.once: raise SystemExit(1)
                    time.sleep(30)
                if args.once: break
                time.sleep(5)
    finally: provider.close()

if __name__ == '__main__': main()
