"""Serialize scheduled and manual source collection for the same database."""
import fcntl
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import text

from .market import MarketError

@contextmanager
def source_lock(bind):
    if bind.dialect.name == 'postgresql':
        with bind.connect() as connection:
            if not connection.scalar(text('SELECT pg_try_advisory_lock(7236921)')):
                raise MarketError('Another data fetch is running. Try again shortly.')
            try: yield
            finally: connection.execute(text('SELECT pg_advisory_unlock(7236921)'))
    else:
        path = Path(bind.url.database).with_suffix('.fetch.lock')
        with path.open('a') as file:
            try: fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MarketError('Another data fetch is running. Try again shortly.') from None
            try: yield
            finally: fcntl.flock(file, fcntl.LOCK_UN)
