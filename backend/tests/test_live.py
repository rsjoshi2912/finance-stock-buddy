import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import market
from app.db import build_engine, initialize
from app.engine import cutoff_for, feature_prices
from app.live import telegram_check, telegram_chats
from app.market import Upstox, MarketError, ingest_daily, import_mapping, refresh_quotes
from app.models import Instrument, InstrumentMapping, Price, Quote, ScheduledRun, Setting
from app.scheduler import due_jobs, execute_once

def universe(session):
    import_mapping(session, 'symbol,name,sector,kind,member_from,member_to,instrument_key\nABC,ABC,Test,stock,2026-01-01,,NSE_EQ|TEST\n')

def test_upstox_adapter_is_read_only_and_redacts_tokens():
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(401, json={'error': 'do not echo this server response'})
    provider = Upstox('secret-test-token', transport=httpx.MockTransport(respond))
    with pytest.raises(MarketError, match='access was rejected') as error:
        provider.quotes(['NSE_EQ|TEST'])
    assert 'secret-test-token' not in str(error.value)
    assert requests[0].method == 'GET'
    with pytest.raises(MarketError, match='Only market-data'):
        provider.get('/v2/order/place')
    assert len(requests) == 1
    provider.close()

def test_quotes_are_separate_from_daily_prices_and_keep_old_timestamps(session):
    universe(session)
    observed = '2026-09-07T05:00:00+00:00'
    payload = {'NSE:ABC': {'instrument_token': 'NSE_EQ|TEST', 'last_price': 101,
        'net_change': 1, 'timestamp': observed}}
    provider = Upstox('fixture', transport=httpx.MockTransport(lambda _: httpx.Response(200,
        json={'status': 'success', 'data': payload})))
    assert refresh_quotes(session, provider, observed) == 1
    assert session.scalar(select(Price)) is None
    assert session.get(Quote, 'ABC').price == 101
    payload['NSE:ABC']['timestamp'] = '2026-09-06T05:00:00+00:00'
    with pytest.raises(MarketError, match='No valid price'):
        refresh_quotes(session, provider, observed)
    assert session.get(Quote, 'ABC').market_at == observed
    provider.close()

def test_candle_receipt_is_after_network_response_and_never_backdated(session, monkeypatch):
    universe(session)
    clock = {'time': '2026-09-07T01:29:00+00:00'}
    monkeypatch.setattr(market, 'now', lambda: clock['time'])
    class DelayedProvider:
        def candles(self, *_):
            clock['time'] = '2026-09-07T01:31:00+00:00'
            return [['2026-09-04T00:00:00+05:30', 100, 102, 99, 101, 1000, 0]]
    result = ingest_daily(session, DelayedProvider(), '2026-09-04')
    assert result['accepted'] == 1
    saved = session.scalar(select(Price))
    assert saved.published_at == saved.ingested_at == clock['time']
    assert feature_prices(session, 'ABC', cutoff=cutoff_for('2026-09-07')) == []

def hours(day='2026-09-07'):
    return {'date': day, 'open': f'{day}T03:45:00+00:00', 'close': f'{day}T10:00:00+00:00'}

@pytest.mark.parametrize('time,expected', [
    ('06:10', ['history']), ('07:20', ['predict']), ('08:30', ['morning']),
    ('08:46', []), ('10:00', ['quotes']), ('18:30', ['close']),
    ('19:00', ['close', 'evening']), ('20:00', []),
])
def test_scheduler_ist_windows(time, expected):
    assert due_jobs(datetime.fromisoformat(f'2026-09-07T{time}:00+05:30'), hours()) == expected

def test_scheduler_holidays_and_special_sessions_do_not_fabricate_morning_calls():
    current = datetime.fromisoformat('2026-09-07T08:30:00+05:30')
    assert due_jobs(current, {'date': '2026-09-07', 'open': None, 'close': None}) == []
    special = {'date': '2026-09-07', 'open': '2026-09-07T12:30:00+00:00', 'close': '2026-09-07T13:30:00+00:00'}
    assert due_jobs(current, special) == []

def test_scheduler_persists_success_and_limits_retries(tmp_path):
    engine = build_engine(f'sqlite:///{tmp_path}/worker.db'); initialize(engine)
    factory = lambda: Session(engine, expire_on_commit=False)
    called = []
    t = datetime(2026, 9, 7, 2, tzinfo=timezone.utc)
    assert execute_once(factory, 'predict:2026-09-07', lambda s: called.append(1), t)
    assert not execute_once(factory, 'predict:2026-09-07', lambda s: called.append(2), t + timedelta(minutes=2))
    assert called == [1]
    def failing(_): raise MarketError('Provider unavailable')
    for offset in (0, 2, 4, 6):
        assert not execute_once(factory, 'history:2026-09-07', failing, t + timedelta(minutes=offset))
    with factory() as session:
        assert session.get(ScheduledRun, 'history:2026-09-07').attempts == 3
    engine.dispose()

def test_telegram_check_verifies_private_chat_without_sending(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'fixture-token')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', '123')
    paths = []
    def respond(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={'ok': True, 'result': {'id': 123, 'type': 'private'}})
    result = telegram_check(httpx.MockTransport(respond))
    assert result['private_chat_verified'] and not result['message_sent']
    assert all('sendMessage' not in p for p in paths)

def test_telegram_ambiguous_failure_never_sends_twice(session, monkeypatch):
    from app import jobs
    monkeypatch.setattr(jobs, 'MODE', 'live')
    monkeypatch.setenv('TELEGRAM_ENABLED', 'true')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'fixture-secret')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', '123')
    attempts = []
    session.add(Setting(key='telegram_verified_chat_id', value='123')); session.commit()
    def respond(request):
        attempts.append(request)
        raise httpx.ReadTimeout('contains a sensitive URL', request=request)
    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(jobs.httpx, 'Client', lambda **kwargs: client)
    with pytest.raises(ValueError, match='could not be confirmed'):
        jobs.send_telegram('Fixture', 'morning', '2026-09-07', session)
    with pytest.raises(ValueError, match='already attempted'):
        jobs.send_telegram('Fixture', 'morning', '2026-09-07', session)
    assert len(attempts) == 1

def test_sender_rejects_a_changed_or_unverified_chat(session, monkeypatch):
    from app import jobs
    monkeypatch.setattr(jobs, 'MODE', 'live')
    monkeypatch.setenv('TELEGRAM_ENABLED', 'true')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'fixture-secret')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', '456')
    session.add(Setting(key='telegram_verified_chat_id', value='123')); session.commit()
    with pytest.raises(ValueError, match='telegram-check'):
        jobs.send_telegram('Fixture', 'morning', '2026-09-07', session)

def test_chat_discovery_returns_only_private_start_chat_ids(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','fixture-token')
    updates=[{'message':{'chat':{'type':'private','id':123},'text':'/start'}},
        {'message':{'chat':{'type':'group','id':-456},'text':'/start'}},
        {'message':{'chat':{'type':'private','id':789},'text':'Do not expose this message'}}]
    result=telegram_chats(httpx.MockTransport(lambda request:httpx.Response(200,json={'ok':True,'result':updates})))
    assert result['private_chat_ids']==['123']
    assert not result['message_sent']
    assert 'Do not expose' not in json.dumps(result)
