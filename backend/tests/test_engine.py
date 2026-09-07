import json
from datetime import date,timedelta
from pathlib import Path
import pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DatabaseError
from app.models import Instrument,Price,Prediction,Resolution,Evidence
from app.engine import paper_profit,split_adjust,feature_prices,feature_evidence,make_daily_calls,resolve_day,cutoff_for,utcstamp,capped_judge_probability,can_promote
from app.analytics import dashboard
from app.briefs import morning,evening
from app.ingest import import_prices,import_news
from app.jobs import trading_day,reserve_tokens

@pytest.mark.parametrize('direction,entry,exit,expected', [('UP',100,110,98.5),('DOWN',100,90,98.5),('DOWN',100,110,-101.5),('UP',100,100,-1.5)])
def test_actual_fixed_notional_pnl(direction,entry,exit,expected):
    assert paper_profit(direction,entry,exit)==pytest.approx(expected)

@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf')])
def test_invalid_price(value):
    with pytest.raises(ValueError):paper_profit('UP',value,10)

def test_split_preserves_value():
    raw=[dict(open=200,high=220,low=180,close=210,volume=500)]
    adjusted=split_adjust(raw,2,1)
    assert adjusted[0]['close']==105 and adjusted[0]['volume']==1000
    assert adjusted[0]['close']*adjusted[0]['volume']==raw[0]['close']*raw[0]['volume']
    assert raw[0]['close']==210

def test_every_feature_reader_requires_cutoff(session):
    with pytest.raises(TypeError):feature_prices(session,'ABC')
    with pytest.raises(TypeError):feature_evidence(session,'ABC')
    with pytest.raises(ValueError):feature_prices(session,'ABC',cutoff='2026-09-01T07:00:00')

def test_cutoff_checks_both_publication_and_arrival(session):
    session.add(Instrument(symbol='ABC',name='ABC',sector='Test'));session.flush()
    cutoff=cutoff_for('2026-09-01')
    old=utcstamp('2026-08-31T18:00:00+05:30');late=utcstamp('2026-09-01T07:00:01+05:30')
    for i,(published,ingested) in enumerate([(old,old),(old,late),(late,old)]):
        session.add(Price(symbol='ABC',date=f'2026-08-{29+i}',open=100,high=102,low=99,close=101,volume=10,published_at=published,ingested_at=ingested,source='fixture'))
        session.add(Evidence(symbol='ABC',title=f'News {i}',url=f'https://example.com/{i}',body='',published_at=published,ingested_at=ingested))
    session.flush()
    assert len(feature_prices(session,'ABC',cutoff=cutoff))==1
    assert len(feature_evidence(session,'ABC',cutoff=cutoff))==1

def build_ten_day_fixture(session):
    symbols=[f'TEST{i}' for i in range(10)]
    for s in symbols:session.add(Instrument(symbol=s,name=s,sector='Fixture'))
    session.flush();days=[];day=date(2026,6,1)
    while len(days)<40:
        if day.weekday()<5:days.append(day.isoformat())
        day+=timedelta(days=1)
    previous={s:100 for s in symbols}
    for i,day in enumerate(days):
        if i>=30:assert make_daily_calls(session,day,synthetic=True)==10
        for j,s in enumerate(symbols):
            open_=previous[s]*(1.005 if j<5 else .975);close=open_*1.01;previous[s]=close
            stamp=utcstamp(f'{day}T18:00:00+05:30')
            session.add(Price(symbol=s,date=day,open=open_,close=close,high=close*1.001,low=open_*.999,volume=1000,published_at=stamp,ingested_at=stamp,source='fixture',synthetic=True))
        session.flush()
        if i>=30:assert resolve_day(session,day)==30
    session.commit();return days

def test_full_pipeline_frozen_ten_days_matches_golden(session):
    days=build_ten_day_fixture(session);data=dashboard(session)
    golden=json.loads((Path(__file__).parent/'golden_scorecard.json').read_text())
    for key,value in golden.items():assert data['summary'][key]==pytest.approx(value),(key,data['summary'][key])
    assert len(data['calls'])==10
    assert sum(x['direction']=='UP' for x in data['calls'])==5
    assert sum(x['direction']=='DOWN' for x in data['calls'])==5
    assert not data['verdict']['ready'] and not data['verdict']['fno_unlocked']
    assert resolve_day(session,days[-1])==0
    assert make_daily_calls(session,days[-1],synthetic=True)==0
    assert len(morning(data))<=4000 and len(evening(data))<=4000
    assert all(x['past_total']==9 for x in data['calls'])
    with pytest.raises(DatabaseError):
        session.execute(text("UPDATE predictions SET prob_up = .99"))
    session.rollback()
    with pytest.raises(DatabaseError):
        session.execute(text('DELETE FROM resolutions'))
    session.rollback()

def test_missing_close_stays_pending(session):
    days=build_ten_day_fixture(session)
    following=(date.fromisoformat(days[-1])+timedelta(days=3)).isoformat()
    make_daily_calls(session,following,synthetic=True)
    assert resolve_day(session,following)==0
    assert all(x['result']=='Pending' for x in dashboard(session,following)['calls'])

def test_index_direction_scored_but_no_fictional_trade(session):
    days=build_ten_day_fixture(session)
    instrument=session.get(Instrument,'TEST0');instrument.kind='index';session.commit()
    following=(date.fromisoformat(days[-1])+timedelta(days=3)).isoformat();make_daily_calls(session,following,synthetic=True)
    stamp=utcstamp(f'{following}T18:00:00+05:30')
    session.add(Price(symbol='TEST0',date=following,open=100,close=101,high=102,low=99,volume=0,published_at=stamp,ingested_at=stamp,source='fixture',synthetic=True));session.flush();resolve_day(session,following)
    row=next(x for x in dashboard(session,following)['calls'] if x['symbol']=='TEST0')
    assert row['result']=='Right' and row['pnl'] is None and row['baseline_pnl'] is None

def test_judge_probability_bound():
    assert capped_judge_probability(.55,.95)==pytest.approx(.70)
    assert capped_judge_probability(.55,.05)==pytest.approx(.40)
    assert capped_judge_probability(.55,.95,2)==.95

def test_promotion_requires_matched_out_of_sample_days():
    a=[dict(key=i,date=str(i),prob_up=.5,outcome=1) for i in range(60)]
    b=[dict(key=i,date=str(i),prob_up=.6,outcome=1,out_of_sample=True) for i in range(60)]
    assert can_promote(a,b)
    assert not can_promote(a,b[:59])
    b[0]['out_of_sample']=False;assert not can_promote(a,b)

def test_calendar_fails_closed():
    assert not trading_day('2026-08-15',{'2026':['2026-08-15']})
    assert not trading_day('2026-09-06',{'2026':[]})
    with pytest.raises(ValueError):trading_day('2027-01-01',{'2026':[]})

def test_token_cap_reservation(session):
    assert reserve_tokens(session,'2026-09-07',900,1000)
    assert not reserve_tokens(session,'2026-09-07',101,1000)
    assert reserve_tokens(session,'2026-09-07',100,1000)

def test_quarantine_and_news_deduplication(session):
    session.add(Instrument(symbol='ABC',name='ABC',sector='Test'));session.flush()
    content='symbol,date,open,high,low,close,volume,published_at\nABC,2026-08-31,100,101,99,100,1000,2026-08-31T18:00:00+05:30\nABC,2026-09-01,100,160,99,150,1000,2026-09-01T18:00:00+05:30\n'
    result=import_prices(session,content,'fixture','2026-09-02T00:00:00+00:00')
    assert result==dict(accepted=1,quarantined=1,duplicate=0)
    item=dict(symbol='ABC',title='A company announces results',url='https://example.com/a',published_at='2026-09-01T06:00:00+05:30',body='x'*2500)
    assert import_news(session,[item,{**item,'url':'https://example.com/b'}],'2026-09-01T07:00:00+05:30')==1
    assert len(session.scalar(select(Evidence)).body)==2000
