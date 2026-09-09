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
from app.engine import InsufficientCandidates, daily_candidates, make_daily_calls, resolve_day, utcstamp
from app.models import Instrument, Prediction, Price, Setting, ScheduledRun

DAY='2026-09-09'
NOW=datetime.fromisoformat('2026-09-09T08:30:00+05:30')


def limited_universe(session, count=20, buys=3):
    for i in range(count):
        symbol=f'TEST{i}'
        session.add(Instrument(symbol=symbol,name=symbol,sector='Fixture',member_from='2026-01-01'))
        session.flush()
        for j in range(6):
            day=(date(2026,9,3)+timedelta(days=j)).isoformat()
            price=100+j if i<buys else 100-j
            stamp=utcstamp(f'{day}T18:00:00+05:30')
            session.add(Price(symbol=symbol,date=day,open=price,high=price+1,low=price-1,close=price,volume=1000,
                published_at=stamp,ingested_at=stamp,source='fixture',synthetic=False))
    session.commit()


@pytest.mark.parametrize('count,buys', [(20,3),(20,20),(20,0),(4,1),(1,1),(1,0)])
def test_available_candidates_are_ranked_without_direction_quotas(session,count,buys):
    limited_universe(session,count,buys)
    candidates=daily_candidates(session,DAY,required_price_date='2026-09-08')
    expected=[row for _,row in sorted(candidates,key=lambda item:(-item[0],item[1]['symbol']))[:10]]
    assert make_daily_calls(session,DAY,required_price_date='2026-09-08')==min(count,10)
    session.commit()
    calls=sorted(dashboard(session,DAY)['calls'],key=lambda row:row['rank'])
    assert [row['symbol'] for row in calls]==[row['symbol'] for row in expected]
    assert [row['direction'] for row in calls]==[row['direction'] for row in expected]
    assert [row['rank'] for row in calls]==list(range(1,len(calls)+1))
    assert session.scalar(select(func.count(Prediction.id)))==count*3
    for model in ('baseline_always_up','baseline_momentum_5d'):
        selected=set(session.scalars(select(Prediction.symbol).where(Prediction.model_version==model,Prediction.rank.is_not(None))))
        assert selected=={row['symbol'] for row in calls}
    state=call_status(session,DAY,NOW)
    assert state['status']=='ready' and state['saved_calls']==len(calls)
    policy=json.loads(session.get(Setting,f'daily_selection:{DAY}').value)
    assert policy['policy']=='ranked_available_v1'
    assert (policy['available_buy'],policy['available_sell'])==(buys,count-buys)
    assert policy['selected_buy']+policy['selected_sell']==len(calls)
    before=[(p.id,p.direction,p.prob_up,p.rank,p.data_cutoff) for p in session.scalars(select(Prediction).order_by(Prediction.id))]
    assert make_daily_calls(session,DAY,required_price_date='2026-09-08')==0
    assert before==[(p.id,p.direction,p.prob_up,p.rank,p.data_cutoff) for p in session.scalars(select(Prediction).order_by(Prediction.id))]
    assert json.loads(session.get(Setting,f'daily_selection:{DAY}').value)==policy


def test_no_eligible_candidates_still_records_an_empty_day(session):
    with pytest.raises(InsufficientCandidates) as raised:
        make_daily_calls(session,DAY,required_price_date='2026-09-08')
    assert (raised.value.buy,raised.value.sell)==(0,0)
    assert session.scalar(select(func.count(Prediction.id)))==0
    record_shortfall(session,DAY,raised.value,NOW)
    state=call_status(session,DAY,NOW)
    assert state['status']=='skipped' and state['telegram']=='not_attempted'
    assert state['available_buy']==0 and 'No eligible candidates' in state['reason']
    assert session.get(Setting,f'daily_selection:{DAY}') is None


def test_scheduler_keeps_the_shortfall_reason_after_failed_transaction(session,monkeypatch):
    monkeypatch.setattr(scheduler,'previous_session',lambda *args:'2026-09-08')
    factory=lambda:Session(session.get_bind(),expire_on_commit=False)
    current=NOW.replace(hour=7,minute=20)
    assert not scheduler.execute_once(factory,f'predict:{DAY}',lambda s:scheduler.predict(s,None,DAY,current),current)
    session.expire_all()
    assert 'No eligible candidates' in session.get(ScheduledRun,f'predict:{DAY}').detail
    assert call_status(session,DAY,NOW)['available_buy']==0
    assert session.scalar(select(func.count(Prediction.id)))==0


@pytest.mark.parametrize('count,buys', [(0,0),(1,1),(4,0),(20,3)])
@pytest.mark.parametrize('period', ['morning','evening'])
def test_variable_batch_or_empty_day_sends_exactly_one_note(session,monkeypatch,count,buys,period):
    if count:
        limited_universe(session,count,buys)
        make_daily_calls(session,DAY,required_price_date='2026-09-08')
    else:
        record_shortfall(session,DAY,InsufficientCandidates(0,0),NOW)
    monkeypatch.setattr(jobs,'MODE','live')
    monkeypatch.setenv('TELEGRAM_ENABLED','true');monkeypatch.setenv('TELEGRAM_BOT_TOKEN','fixture-secret');monkeypatch.setenv('TELEGRAM_CHAT_ID','123')
    session.add(Setting(key='telegram_verified_chat_id',value='123'));session.commit()
    sent=[]
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={'ok':True})
    client=httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(jobs.httpx,'Client',lambda **kwargs:client)
    scheduler.deliver(session,DAY,period)
    assert len(sent)==1
    assert ('NO CALLS TODAY' in sent[0]['text'])==(count==0)
    assert session.get(Setting,f'telegram:{period}:{DAY}').value=='sent'
    if count and period=='morning':
        data=dashboard(session,DAY)
        assert all(call['symbol'] in sent[0]['text'] for call in data['calls'])
        for direction,label in [('UP','BUY WATCHLIST'),('DOWN','SELL WATCHLIST')]:
            assert (label in sent[0]['text'])==any(call['direction']==direction for call in data['calls'])
    with pytest.raises(ValueError,match='already attempted'):scheduler.deliver(session,DAY,period)
    assert len(sent)==1 and session.scalar(select(func.count(Prediction.id)))==count*3


def test_short_batch_scores_only_selected_stocks_and_matching_baseline(session):
    limited_universe(session,4,1)
    make_daily_calls(session,DAY,required_price_date='2026-09-08')
    stamp=utcstamp(f'{DAY}T18:00:00+05:30')
    for i in range(4):
        session.add(Price(symbol=f'TEST{i}',date=DAY,open=100,high=102,low=99,close=101,volume=1000,
            published_at=stamp,ingested_at=stamp,source='fixture',synthetic=False))
    session.flush()
    assert resolve_day(session,DAY)==12
    stats=dashboard(session,DAY)['summary']
    assert stats['total']==4 and stats['costs']==6
    assert stats['pnl']==-26 and stats['baseline_pnl']==34
    assert dashboard(session,DAY)['today_summary']==stats


def test_old_skip_diagnostic_and_delivery_claim_are_not_rewritten(session):
    original=json.dumps(dict(status='skipped',reason='Only 3 Buy and 17 Sell candidates qualified. The daily batch needs at least 5 of each; no calls were published.',available_buy=3,available_sell=17))
    session.add(Setting(key=f'daily_calls:{DAY}',value=original))
    session.add(Setting(key=f'telegram:morning:{DAY}',value='sent'))
    session.commit()
    assert call_status(session,DAY,NOW)['available_buy']==3
    assert call_status(session,DAY,NOW)['telegram']=='sent'
    assert session.get(Setting,f'daily_calls:{DAY}').value==original
    assert session.scalar(select(func.count(Prediction.id)))==0


@pytest.mark.parametrize('day,current', [(DAY,NOW),("2026-09-08",NOW.replace(hour=7,minute=20))])
def test_relaxed_selection_does_not_allow_late_or_backdated_calls(session,day,current):
    limited_universe(session,1,1)
    with pytest.raises(scheduler.MarketError,match='window has passed'):
        scheduler.predict(session,None,day,current)
    assert session.scalar(select(func.count(Prediction.id)))==0


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
    record_shortfall(session,DAY,InsufficientCandidates(0,0),NOW)
    assert main.today(session=session)['date']==DAY
    assert main.today(date='2026-09-08',session=session)['date']=='2026-09-08'
    assert main.today(session=session)['calls']==[]
    assert 'NO CALLS TODAY' in main.brief('morning',session=session)['text']
    assert 'No eligible candidates' in main.today(session=session)['daily_status']['reason']
