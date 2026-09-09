from datetime import date, datetime, timedelta
import json
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app import jobs, scheduler
from app.analytics import dashboard
from app.briefs import morning, evening
from app.daily_status import call_status, record_shortfall
from app.engine import InsufficientCandidates, daily_candidates, make_daily_calls, utcstamp
from app.models import Instrument, Prediction, Price, Setting, ScheduledRun

DAY='2026-09-09'
NOW=datetime.fromisoformat('2026-09-09T08:30:00+05:30')


def limited_universe(session):
    for i in range(20):
        symbol=f'TEST{i}'
        session.add(Instrument(symbol=symbol,name=symbol,sector='Fixture',member_from='2026-01-01'))
        session.flush()
        for j in range(6):
            day=(date(2026,9,3)+timedelta(days=j)).isoformat()
            price=100+j if i<3 else 100-j
            stamp=utcstamp(f'{day}T18:00:00+05:30')
            session.add(Price(symbol=symbol,date=day,open=price,high=price+1,low=price-1,close=price,volume=1000,
                published_at=stamp,ingested_at=stamp,source='fixture',synthetic=False))
    session.commit()


def test_shortfall_is_explicit_and_never_saves_partial_or_relabelled_calls(session):
    limited_universe(session)
    candidates=daily_candidates(session,DAY,required_price_date='2026-09-08')
    assert len(candidates)==20
    with pytest.raises(InsufficientCandidates) as raised:
        make_daily_calls(session,DAY,required_price_date='2026-09-08')
    assert (raised.value.buy,raised.value.sell)==(3,17)
    assert session.scalar(select(func.count(Prediction.id)))==0
    record_shortfall(session,DAY,raised.value,NOW)
    state=call_status(session,DAY,NOW)
    assert state['status']=='skipped' and state['telegram']=='not_attempted'
    assert state['available_buy']==3 and '3 Buy and 17 Sell' in state['reason']


def test_scheduler_keeps_the_shortfall_reason_after_failed_transaction(session,monkeypatch):
    limited_universe(session)
    monkeypatch.setattr(scheduler,'previous_session',lambda *args:'2026-09-08')
    factory=lambda:Session(session.get_bind(),expire_on_commit=False)
    current=NOW.replace(hour=7,minute=20)
    assert not scheduler.execute_once(factory,f'predict:{DAY}',lambda s:scheduler.predict(s,None,DAY,current),current)
    session.expire_all()
    assert '3 Buy and 17 Sell' in session.get(ScheduledRun,f'predict:{DAY}').detail
    assert call_status(session,DAY,NOW)['available_buy']==3
    assert session.scalar(select(func.count(Prediction.id)))==0


def test_skipped_day_sends_one_status_note_without_publishing_calls(session,monkeypatch):
    record_shortfall(session,DAY,InsufficientCandidates(3,17),NOW)
    monkeypatch.setattr(jobs,'MODE','live')
    monkeypatch.setenv('TELEGRAM_ENABLED','true');monkeypatch.setenv('TELEGRAM_BOT_TOKEN','fixture-secret');monkeypatch.setenv('TELEGRAM_CHAT_ID','123')
    session.add(Setting(key='telegram_verified_chat_id',value='123'));session.commit()
    sent=[]
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={'ok':True})
    client=httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(jobs.httpx,'Client',lambda **kwargs:client)
    scheduler.deliver(session,DAY,'morning')
    assert len(sent)==1 and 'NO CALLS TODAY' in sent[0]['text'] and '3 Buy and 17 Sell' in sent[0]['text']
    assert 'SELL WATCHLIST' not in sent[0]['text']
    assert call_status(session,DAY,NOW)['telegram']=='sent'
    with pytest.raises(ValueError,match='already attempted'):scheduler.deliver(session,DAY,'morning')
    assert len(sent)==1 and session.scalar(select(func.count(Prediction.id)))==0


def test_missing_day_preview_does_not_replay_old_calls_or_claim_pending_results(session):
    data=dashboard(session,DAY)
    assert 'NO CALLS TODAY' in morning(data)
    assert 'NO CALLS TODAY' in evening(data) and 'Results pending' not in evening(data)
    assert session.get(Setting,f'telegram:morning:{DAY}') is None


def test_live_today_uses_ist_date_without_changing_historical_selection(session,monkeypatch):
    from app import main
    class Clock:
        @staticmethod
        def now(tz):return NOW
    monkeypatch.setattr(main,'MODE','live');monkeypatch.setattr(main,'datetime',Clock)
    record_shortfall(session,DAY,InsufficientCandidates(3,17),NOW)
    assert main.today(session=session)['date']==DAY
    assert main.today(date='2026-09-08',session=session)['date']=='2026-09-08'
    assert main.today(session=session)['calls']==[]
    assert 'NO CALLS TODAY' in main.brief('morning',session=session)['text']
    assert '3 Buy' in main.today(session=session)['daily_status']['reason']
