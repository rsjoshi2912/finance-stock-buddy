"""Scheduled and owner-triggered index collection share the existing source lock."""
from datetime import datetime, timedelta

from .db import SessionLocal
from .fetch_lock import source_lock
from .index_research import collect_and_assess, clock
from .models import JobRun
from .refresh import save_progress, safe_error

REFRESH_KEY = 'manual_index_fetch'


def index_job_due(current, hours):
    if not hours.get('open'): return False
    opened, closed = (datetime.fromisoformat(hours[k]) for k in ('open','close'))
    return opened + timedelta(minutes=5) <= current <= closed + timedelta(minutes=5) and current.second >= 15


def run_index_refresh(request_id, factory=SessionLocal):
    if not save_progress(factory,request_id,key=REFRESH_KEY,status='running',message='Checking Nifty and Bank Nifty…'): return
    results = []
    try:
        with factory() as session:
            with source_lock(session.get_bind()): results = collect_and_assess(session)
        good = sum(row['status']=='ok' for row in results)
        status = 'complete' if good == 2 else 'partial' if good else 'failed'
        message = 'Index checks saved.' if good == 2 else 'Some index data is unavailable. Each card explains its status.'
    except Exception as error:
        status, message = 'failed', safe_error(error)
    finished = clock().isoformat(timespec='seconds')
    if save_progress(factory,request_id,key=REFRESH_KEY,status=status,stage='finished',message=message,
                     indices=results,completed_at=finished):
        with factory() as session:
            session.add(JobRun(job='index refresh',status='ok' if status=='complete' else 'warning',rows=len(results),detail=message,started_at=finished))
            session.commit()
