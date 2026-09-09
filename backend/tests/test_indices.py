import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app import index_research as research
from app.db import session_dependency
from app.engine import utcstamp
from app.index_jobs import index_job_due
from app.index_options import assess_option, paper_limits
from app.index_research import evaluate_index, feature_candles, ingest_candles, save_assessment, snapshot
from app.index_sources import OptionSource, index_candles
from app.market import IST, MarketError, Upstox
from app.models import IndexAssessment, IndexCandle, Prediction, Price, Setting
from app.refresh import request_refresh, refresh_status

CURRENT = datetime.fromisoformat('2026-09-09T09:40:30+05:30')


def hours(day):
    return {'date':day,'open':f'{day}T09:15:00+05:30' if date.fromisoformat(day).weekday()<5 else None,
            'close':f'{day}T15:30:00+05:30' if date.fromisoformat(day).weekday()<5 else None}


def candles(down=False):
    result=[]
    for day, count in [('2026-09-07',75),('2026-09-08',75),('2026-09-09',5)]:
        for i in range(count):
            start=datetime.fromisoformat(f'{day}T09:15:00+05:30')+timedelta(minutes=5*i)
            values=(20980,20982,20978,20980)
            if day=='2026-09-09':
                values=[(21010,21050,21000,21020),(21020,21040,21005,21025),(21025,21040,21010,21020),
                        (21025,21065,21020,21060),(21055,21075,21048,21070)][i]
            o,h,l,c=values
            if down:o,h,l,c=42050-o,42050-l,42050-h,42050-c
            result.append(IndexCandle(id=len(result)+1,symbol='NIFTY',source='Yahoo Finance',start_at=utcstamp(start.isoformat()),
                end_at=utcstamp((start+timedelta(minutes=5)).isoformat()),open=o,high=h,low=l,close=c,
                received_at=utcstamp(CURRENT.isoformat()),content_hash=str(len(result))))
    return result


def quote(current=CURRENT, **changes):
    return dict(symbol='NIFTY',side='CE',instrument='NSE_FO|123',name='NIFTY TEST CE',expiry='2026-09-15',strike=21050,
        lot=65,tick=.05,bid=79.5,ask=80,bid_qty=100,ask_qty=100,volume=1000,oi=1000,
        quote_at=utcstamp(current.isoformat()),received_at=utcstamp(current.isoformat()),source='Upstox',contract_verified=True,**changes)


@pytest.mark.parametrize('down,expected',[(False,'UP'),(True,'DOWN')])
def test_direction_requires_an_opening_break_retest_and_matching_trend(down,expected):
    bars=candles(down)
    result=evaluate_index('NIFTY',bars,CURRENT,hours)
    assert result['direction']==expected and result['validated'] is False
    assert result['candle_ids'] and result['news_used'] is False
    assert result['valid_until']=='2026-09-09T04:20:00+00:00'
    # Crossing the range without holding the very next retest is not a setup.
    if down:bars[-1].high=21020
    else:bars[-1].low=21020
    assert evaluate_index('NIFTY',bars,CURRENT,hours)['direction']=='SKIP'


def test_missing_candles_forming_bars_stale_data_and_closed_markets_fail_closed(session):
    bars=candles()
    assert 'missing' in evaluate_index('NIFTY',bars[:80]+bars[81:],CURRENT,hours)['reason']
    assert 'old' in evaluate_index('NIFTY',bars,CURRENT+timedelta(minutes=11),hours)['reason']
    assert 'closed' in evaluate_index('NIFTY',bars,CURRENT.replace(hour=18),hours)['reason']
    assert '14:45' in evaluate_index('NIFTY',bars,CURRENT.replace(hour=14,minute=45),hours)['reason']
    rows=[{key:getattr(bars[-1],key) for key in ('start_at','open','high','low','close')},
          dict(start_at='2026-09-09T09:40:00+05:30',open=21070,high=21080,low=21060,close=21075)]
    assert ingest_candles(session,'NIFTY',rows,CURRENT.isoformat(),hours)==1
    assert len(feature_candles(session,'NIFTY',CURRENT.isoformat()))==1
    assert feature_candles(session,'NIFTY',(CURRENT-timedelta(seconds=1)).isoformat())==[]
    assert session.scalar(select(Price)) is None and session.scalar(select(Prediction)) is None


def test_revisions_only_affect_later_reads_and_assessments_cannot_be_rewritten(session):
    row=dict(start_at='2026-09-09T09:35:00+05:30',open=21055,high=21075,low=21048,close=21070)
    assert ingest_candles(session,'NIFTY',[row],CURRENT.isoformat(),hours)==1
    assert ingest_candles(session,'NIFTY',[row],CURRENT.isoformat(),hours)==0
    row['close']=21065
    assert ingest_candles(session,'NIFTY',[row],(CURRENT+timedelta(minutes=1)).isoformat(),hours)==1
    assert feature_candles(session,'NIFTY',CURRENT.isoformat())[-1].close==21070
    assert feature_candles(session,'NIFTY',(CURRENT+timedelta(minutes=2)).isoformat())[-1].close==21065
    # A provider can restore the original value. Record that later observation
    # instead of deduplicating it against all history and leaving the correction active.
    row['close']=21070
    assert ingest_candles(session,'NIFTY',[row],(CURRENT+timedelta(minutes=3)).isoformat(),hours)==1
    assert feature_candles(session,'NIFTY',(CURRENT+timedelta(minutes=2)).isoformat())[-1].close==21065
    assert feature_candles(session,'NIFTY',(CURRENT+timedelta(minutes=4)).isoformat())[-1].close==21070
    payload=evaluate_index('NIFTY',candles(),CURRENT,hours)
    payload['option']=assess_option('UP',None,CURRENT)
    saved=save_assessment(session,payload);session.commit()
    later=snapshot(session,CURRENT+timedelta(minutes=11))['indices'][0]
    assert later['direction']=='SKIP' and later['saved_direction']=='UP'
    assert session.get(IndexAssessment,saved.id).direction=='UP'
    with pytest.raises(IntegrityError):session.execute(update(IndexAssessment).values(direction='DOWN'))
    session.rollback()
    with pytest.raises(IntegrityError):session.execute(update(IndexCandle).values(close=1))
    session.rollback()


def test_option_check_has_a_real_positive_path_but_small_capital_is_skipped():
    limits={'valid':True,'capital':200000,'risk':2000,'costs':60}
    result=assess_option('UP',quote(),CURRENT,limits)
    assert result['action']=='BUY_CALL' and result['lot']==65 and result['entry']==80
    assert result['stop']==64 and result['target']==112
    assert result['planned_loss']==1100 and result['target_net']==2020 and result['premium_at_risk']==5260
    assert assess_option('UP',quote(),CURRENT,{'valid':True,'capital':10000,'risk':100,'costs':60})['action']=='SKIP'
    put=quote();put['side']='PE'
    assert assess_option('DOWN',put,CURRENT,limits)['action']=='BUY_PUT'
    assert assess_option('UP',None,CURRENT)['action']=='SKIP'


@pytest.mark.parametrize('field,value',[
    ('quote_at','2026-09-09T03:00:00+00:00'),('quote_at','2026-09-09T10:00:00+00:00'),
    ('received_at','2026-09-09T03:00:00+00:00'),('expiry','2026-09-09'),('bid',81),('bid',60),
    ('lot',1.5),('lot',True),('bid_qty',1),('volume',0),('tick',float('nan')),('side','PE'),('contract_verified',False)])
def test_option_check_rejects_old_invalid_or_wrong_contract_data(field,value):
    item=quote();item[field]=value
    assert assess_option('UP',item,CURRENT,{'valid':True,'capital':200000,'risk':2000,'costs':60})['action']=='SKIP'


def test_source_failure_on_one_index_preserves_the_other_and_never_sends(session,monkeypatch):
    provider=SimpleNamespace(close=lambda:None)
    monkeypatch.setattr(research,'hours_for',lambda s,p:hours)
    monkeypatch.setattr(research,'clock',lambda:CURRENT)
    monkeypatch.setenv('INDEX_OPTION_PROVIDER','none')
    def fetch(provider,symbol):
        if symbol=='BANKNIFTY':raise RuntimeError('secret cookie must not be returned')
        return [{key:getattr(b,key) for key in ('start_at','open','high','low','close')} for b in candles()]
    monkeypatch.setattr(research,'index_candles',fetch)
    result=research.collect_and_assess(session,provider)
    assert [x['status'] for x in result]==['ok','failed']
    rows=session.scalars(select(IndexAssessment).order_by(IndexAssessment.id)).all()
    assert [x.direction for x in rows]==['UP','SKIP']
    assert 'secret' not in rows[1].payload
    assert session.scalar(select(Price)) is None and session.scalar(select(Prediction)) is None
    assert not session.scalar(select(Setting).where(Setting.key.startswith('telegram:')))


def test_index_api_auth_separate_refresh_state_and_preview(session,monkeypatch):
    from app import main,refresh
    from app.index_jobs import REFRESH_KEY
    monkeypatch.setenv('OWNER_PASSWORD','fixture-only');monkeypatch.setattr(refresh,'MODE','live');monkeypatch.setattr(main,'MODE','live')
    session.add(Setting(key='dataset_mode',value='live'));session.commit()
    main.app.dependency_overrides[session_dependency]=lambda:session
    queued=[];monkeypatch.setattr(main,'run_index_refresh',lambda id:queued.append(id))
    try:
        client=TestClient(main.app)
        auth=('ravi','fixture-only')
        assert client.get('/api/indices').status_code==401
        assert client.post('/api/indices/refresh',json={}).status_code==401
        assert client.post('/api/indices/refresh',json={},auth=auth,headers={'Origin':'https://untrusted.test'}).status_code==403
        initial=client.post('/api/indices/refresh',json={},auth=auth)
        assert initial.status_code==202
        again=client.post('/api/indices/refresh',json={},auth=auth)
        assert again.json()['id']==initial.json()['id'] and len(queued)==1
        assert refresh_status(session,key=REFRESH_KEY)['busy']
        assert not refresh_status(session)['busy']
        assert client.get('/api/indices/brief',auth=auth).json()['sent'] is False
    finally:client.close();main.app.dependency_overrides.clear()


def test_scheduler_index_window_has_no_holiday_or_opening_catchup():
    assert not index_job_due(CURRENT,{'open':None,'close':None})
    assert not index_job_due(CURRENT.replace(hour=9,minute=16),hours('2026-09-09'))
    assert index_job_due(CURRENT,hours('2026-09-09'))
    assert not index_job_due(CURRENT.replace(second=5),hours('2026-09-09'))
    assert not index_job_due(CURRENT.replace(hour=16),hours('2026-09-09'))


def test_optional_broker_adapter_uses_exact_contract_and_timestamped_depth():
    paths=[]
    contract=dict(name='NIFTY',segment='NSE_FO',exchange='NSE',expiry='2026-09-15',instrument_key='NSE_FO|123',
        trading_symbol='NIFTY 21050 CE',tick_size=5,lot_size=65,instrument_type='CE',underlying_key='NSE_INDEX|Nifty 50',
        underlying_type='INDEX',strike_price=21050)
    def respond(request):
        paths.append(request.url.path)
        data=[contract] if request.url.path.endswith('/contract') else {'NSE:TEST':dict(instrument_token='NSE_FO|123',
            depth={'buy':[{'price':79.5,'quantity':100}],'sell':[{'price':80,'quantity':100}]},volume=1000,oi=1000,timestamp=CURRENT.isoformat())}
        return httpx.Response(200,json={'status':'success','data':data})
    provider=Upstox('fixture',transport=httpx.MockTransport(respond));source=OptionSource(provider)
    try:
        result=source.candidate('NIFTY','CE',21055,CURRENT)
        assert result['lot']==65 and result['tick']==.05 and result['instrument']=='NSE_FO|123'
        assert result['quote_at']==utcstamp(CURRENT.isoformat())
        assert paths==['/v2/option/contract','/v2/market-quote/quotes']
    finally:source.close()


@pytest.mark.parametrize('field,value',[('tick',float('nan')),('strike',float('inf')),('name',None),('lot',True)])
def test_bad_option_quote_can_still_be_saved_as_a_skip(session,field,value):
    item=quote();item[field]=value
    payload=evaluate_index('NIFTY',candles(),CURRENT,hours)
    payload['option']=assess_option('UP',item,CURRENT,{'valid':True,'capital':200000,'risk':2000,'costs':60})
    assert payload['option']['action']=='SKIP'
    row=save_assessment(session,payload);session.commit()
    assert json.loads(row.payload)['option']['contract'] is None


def test_index_preview_uses_ist_and_escapes_contract_name():
    from app import briefs
    payload=evaluate_index('NIFTY',candles(),CURRENT,hours)
    item=quote();item['name']='<script> & fixture'
    payload['option']=assess_option('UP',item,CURRENT,{'valid':True,'capital':200000,'risk':2000,'costs':60})
    html=briefs.indices({'indices':[payload]})
    assert '09 Sep 09:40:30 IST' in html
    assert '&lt;script&gt; &amp; fixture' in html and '<script>' not in html
