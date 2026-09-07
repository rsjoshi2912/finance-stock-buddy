import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import refresh
from app.db import build_engine, initialize, session_dependency
from app.fetch_lock import source_lock
from app.market import MarketError
from app.models import Instrument, JobRun, Prediction, Quote, Setting
from app.scheduler import execute_once

@pytest.fixture
def workspace(tmp_path, monkeypatch):
    engine = build_engine(f'sqlite:///{tmp_path}/manual.db'); initialize(engine)
    factory = lambda: Session(engine, expire_on_commit=False)
    monkeypatch.setattr(refresh, 'MODE', 'live')
    monkeypatch.setenv('OWNER_PASSWORD', 'fixture-only-password')
    monkeypatch.setenv('NEWS_ENABLED', 'true')
    with factory() as session:
        session.add(Setting(key='dataset_mode', value='live'))
        session.add(Instrument(symbol='ABC', name='ABC Limited', sector='Test', kind='stock', member_from='2026-01-01'))
        session.flush()
        session.add(Prediction(symbol='ABC', date='2026-09-07', data_cutoff='2026-09-07T01:30:00+00:00',
            horizon='open_close', direction='UP', prob_up=.55, expected_low=95, expected_high=105,
            invalidation=94, ref_price=100, rank=1, rationale='Frozen morning call',
            model_version='momentum_research_v1', sources='[]', synthetic=False))
        session.commit()
    yield factory, engine
    engine.dispose()

def test_simultaneous_requests_start_only_one_fetch(workspace):
    factory, _ = workspace
    barrier = Barrier(2)
    def claim(_):
        with factory() as session:
            barrier.wait(timeout=5)
            return refresh.request_refresh(session)
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(claim, [1, 2]))
    assert sum(created for _, created in results) == 1
    assert results[0][0]['id'] == results[1][0]['id']

def test_finished_fetch_has_cooldown_and_interrupted_fetch_can_be_retried(workspace):
    factory, _ = workspace; now = datetime.now(timezone.utc)
    with factory() as session: state, _ = refresh.request_refresh(session, now)
    refresh.save_progress(factory, state['id'], status='complete', completed_at=now.isoformat())
    with factory() as session:
        with pytest.raises(refresh.RefreshCooldown) as error: refresh.request_refresh(session, now + timedelta(seconds=10))
        assert error.value.seconds == 50
        next_state, created = refresh.request_refresh(session, now + timedelta(seconds=61))
        assert created and next_state['id'] != state['id']
        final, created = refresh.request_refresh(session, now + timedelta(seconds=700))
        assert created and final['id'] != next_state['id']
    assert not refresh.save_progress(factory, state['id'], status='complete')

@pytest.mark.parametrize('fails', [None, 'prices', 'news'])
def test_refresh_saves_available_data_without_changing_calls(workspace, monkeypatch, fails):
    factory, _ = workspace
    def prices(session, provider):
        if fails == 'prices': raise RuntimeError('sensitive-provider-cookie')
        session.add(Quote(symbol='ABC', price=101, change=1, market_at='2026-09-07T05:00:00+00:00',
            received_at='2026-09-07T05:01:00+00:00', provider='Yahoo Finance'))
        return 1
    def news(session):
        if fails == 'news': raise RuntimeError('sensitive-provider-cookie')
        session.add(Setting(key='news-observed', value='yes'))
        return [{'source': 'Fixture', 'status': 'ok', 'added': 2}]
    monkeypatch.setattr(refresh, 'create_provider', lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(refresh, 'refresh_quotes', prices)
    monkeypatch.setattr(refresh, 'collect_news', news)
    with factory() as session: state, _ = refresh.request_refresh(session)
    refresh.run_refresh(state['id'], factory)
    with factory() as session:
        result = refresh.refresh_status(session)
        assert result['status'] == ('complete' if fails is None else 'partial')
        assert bool(session.get(Quote, 'ABC')) == (fails != 'prices')
        assert bool(session.get(Setting, 'news-observed')) == (fails != 'news')
        call = session.scalar(select(Prediction))
        assert call.rationale == 'Frozen morning call' and call.prob_up == .55
        assert len(session.scalars(select(Prediction)).all()) == 1
        assert not session.scalar(select(Setting).where(Setting.key.startswith('telegram:')))
        assert 'sensitive-provider-cookie' not in json.dumps(result)
        assert session.scalar(select(JobRun)).job == 'manual refresh'

def test_scheduler_and_manual_fetch_share_the_source_lock(workspace, monkeypatch):
    factory, engine = workspace; called = []
    monkeypatch.setattr(refresh, 'create_provider', lambda: called.append('network'))
    with factory() as session: state, _ = refresh.request_refresh(session)
    with source_lock(engine):
        assert not execute_once(factory, 'quotes:fixture', lambda _: called.append('scheduled'))
        refresh.run_refresh(state['id'], factory)
    assert called == []
    with factory() as session:
        assert refresh.refresh_status(session)['status'] == 'failed'
        assert 'Another data fetch' in refresh.refresh_status(session)['message']
    with source_lock(engine): pass  # The lock was released, including after failure.

def test_refresh_endpoint_requires_owner_and_joins_existing_request(workspace, monkeypatch):
    from app import main
    factory, _ = workspace; started = []
    def dependency():
        with factory() as session: yield session
    main.app.dependency_overrides[session_dependency] = dependency
    monkeypatch.setattr(main, 'run_refresh', lambda request_id: started.append(request_id))
    client = TestClient(main.app)
    try:
        assert client.post('/api/refresh', json={}).status_code == 401
        auth = ('ravi', 'fixture-only-password')
        assert client.post('/api/refresh', json={}, auth=auth, headers={'Origin': 'https://untrusted.example'}).status_code == 403
        first = client.post('/api/refresh', json={}, auth=auth)
        assert first.status_code == 202 and first.json()['busy']
        second = client.post('/api/refresh', json={}, auth=auth)
        assert second.json()['id'] == first.json()['id'] and len(started) == 1
        assert client.get('/api/refresh', auth=auth).json()['busy']
        refresh.save_progress(factory, started[0], status='complete', completed_at=refresh.current_time().isoformat())
        assert client.post('/api/refresh', json={}, auth=auth).status_code == 429
        monkeypatch.setattr(refresh, 'MODE', 'demo')
        assert client.post('/api/refresh', json={}, auth=auth).status_code == 409
    finally:
        client.close(); main.app.dependency_overrides.clear()
