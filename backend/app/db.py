from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import DATABASE_URL, ROOT

class Base(DeclarativeBase):
    pass

def build_engine(url=DATABASE_URL):
    ROOT.joinpath('data').mkdir(exist_ok=True)
    engine = create_engine(url, connect_args={'check_same_thread': False,'timeout':30} if url.startswith('sqlite') else {}, pool_pre_ping=True)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def configure(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
    return engine

engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def initialize(target=engine):
    from . import models  # noqa: F401
    with target.begin() as conn:
        if target.dialect.name == 'postgresql':
            # API and worker may start together on a new server.
            conn.execute(text('SELECT pg_advisory_xact_lock(7236920)'))
        Base.metadata.create_all(conn)
        if target.dialect.name == 'sqlite':
            for table in ('predictions', 'resolutions'):
                for action in ('UPDATE', 'DELETE'):
                    conn.execute(text(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Recorded calls and results cannot be changed'); END"))
        elif target.dialect.name == 'postgresql':
            conn.execute(text("CREATE OR REPLACE FUNCTION reject_record_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Recorded calls and results cannot be changed'; END; $$"))
            for table in ('predictions', 'resolutions'):
                conn.execute(text(f'DROP TRIGGER IF EXISTS immutable_record ON {table}'))
                conn.execute(text(f'CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_record_change()'))

def session_dependency():
    with SessionLocal() as session:
        yield session
