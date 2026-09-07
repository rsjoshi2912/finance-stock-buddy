"""Deterministic synthetic market. Nothing in this module is a real market result."""
import math
import random
from datetime import date,timedelta
from sqlalchemy import select
from .engine import make_daily_calls,resolve_day,utcstamp
from .models import Instrument,Price,ModelVersion,Improvement,JobRun,Setting

SYMBOLS=[
 ('RELIANCE','Reliance Industries','Energy',1400),('TCS','Tata Consultancy Services','Technology',3300),
 ('HDFCBANK','HDFC Bank','Banking',950),('INFY','Infosys','Technology',1550),
 ('ICICIBANK','ICICI Bank','Banking',1320),('BHARTIARTL','Bharti Airtel','Telecom',1840),
 ('ITC','ITC Limited','Consumer goods',425),('LT','Larsen & Toubro','Industrials',3700),
 ('SBIN','State Bank of India','Banking',810),('TATAMOTORS','Tata Motors','Auto',720),
 ('SUNPHARMA','Sun Pharmaceutical','Healthcare',1700),('AXISBANK','Axis Bank','Banking',1140),
 ('HINDUNILVR','Hindustan Unilever','Consumer goods',2380),('MARUTI','Maruti Suzuki','Auto',12100),
 ('TITAN','Titan Company','Consumer goods',3550),('WIPRO','Wipro','Technology',280),
 ('BAJFINANCE','Bajaj Finance','Finance',930),('HCLTECH','HCL Technologies','Technology',1670),
 ('NTPC','NTPC Limited','Energy',340),('POWERGRID','Power Grid','Energy',290),
 ('ADANIPORTS','Adani Ports','Industrials',1400),('COALINDIA','Coal India','Energy',420),
 ('NIFTY','Nifty 50','Index',24500),('BANKNIFTY','Bank Nifty','Index',53000)]

def seed_demo(session, days=100):
    mode=session.get(Setting,'dataset_mode')
    if mode:
        if mode.value!='demo': raise ValueError('Use a separate database for sample data')
        return
    if session.scalar(select(Price.id).limit(1)):
        raise ValueError('Refusing to add sample data to a non-empty database')
    session.add(Setting(key='dataset_mode',value='demo'))
    session.add(ModelVersion(name='momentum_research_v1',status='champion',created_at='2026-05-01T00:00:00+00:00',description='Five-day price trend · uncalibrated research rule · sample data',brier=None))
    for symbol,name,sector,start in SYMBOLS:
        session.add(Instrument(symbol=symbol,name=name,sector=sector,kind='index' if sector=='Index' else 'stock'))
    session.flush()
    sessions=[]
    day=date(2026,9,7)
    while len(sessions)<days:
        if day.weekday()<5: sessions.append(day.isoformat())
        day-=timedelta(days=1)
    sessions.reverse()
    rng=random.Random(73)
    previous={s:price for s,_,_,price in SYMBOLS}
    for i,day in enumerate(sessions):
        # Today's forecasts are made BEFORE today's outcomes are generated.
        if i>=30:
            try: make_daily_calls(session,day,synthetic=True)
            except ValueError as exc:
                # No invented direction or silently relabelled selection.
                session.add(JobRun(job='sample forecast',status='warning',rows=0,detail=str(exc),started_at=utcstamp(f'{day}T07:30:00+05:30')))
        if i==len(sessions)-1: break
        for j,(symbol,_,_,_) in enumerate(SYMBOLS):
            drift=.0019*math.sin(i/10+j*.63)
            open_=previous[symbol]*(1+rng.gauss(0,.0035))
            change=drift+rng.gauss(0,.0105)
            close=open_*(1+change)
            high=max(open_,close)*(1+abs(rng.gauss(0,.004)))
            low=min(open_,close)*(1-abs(rng.gauss(0,.004)))
            previous[symbol]=close
            stamp=utcstamp(f'{day}T18:00:00+05:30')
            session.add(Price(symbol=symbol,date=day,open=round(open_,2),close=round(close,2),high=round(high,2),low=round(low,2),volume=rng.randint(100000,8000000),published_at=stamp,ingested_at=stamp,source='synthetic://fixed-seed-73',synthetic=True))
        session.flush()
        resolve_day(session,day)
    for title,detail in [
      ('Does waiting 15 minutes help?','Compare a 09:30 entry with the current open entry using intraday data. Keep the original calls and their scores untouched.'),
      ('Give results days their own check','Test whether calls behave differently around company results. Use announcements known before the morning cutoff.'),
      ('Check whether confidence is too high','Evaluate a probability adjustment on a later, separate time window. Never fit it on the days used to report its accuracy.')]:
        session.add(Improvement(title=title,detail=detail,created_at='2026-09-04T13:30:00+00:00'))
    session.add(JobRun(job='sample data',status='ok',rows=(days-1)*len(SYMBOLS),detail='Generated reproducible example prices; not NSE data.',started_at='2026-09-07T01:00:00+00:00'))
    session.commit()
