import json
from collections import defaultdict,Counter
from sqlalchemy import func,select
from .models import Prediction,Resolution,Instrument,ModelVersion,JobRun,Improvement,TokenBudget,RawRecord,Setting

def records(session, before=None, symbol=None):
    query=select(Prediction,Resolution,Instrument).join(Instrument,Instrument.symbol==Prediction.symbol).outerjoin(Resolution,Resolution.prediction_id==Prediction.id).where(~Prediction.model_version.startswith('baseline_'))
    if before:query=query.where(Prediction.date<=before)
    if symbol:query=query.where(Prediction.symbol==symbol)
    return session.execute(query.order_by(Prediction.date,Prediction.direction.desc(),Prediction.rank)).all()

def serialize(p,r,instrument,history):
    days=sorted({row[0].date for row in history if row[0].date<p.date})[-60:]
    earlier=[row for row in history if row[0].symbol==p.symbol and row[0].model_version==p.model_version
        and row[0].date in days and row[1] and row[1].resolved_at<=p.data_cutoff and row[1].right is not None]
    return dict(id=p.id,symbol=p.symbol,name=instrument.name,sector=instrument.sector,kind=instrument.kind,date=p.date,
        direction=p.direction,confidence=round(100*(p.prob_up if p.direction=='UP' else 1-p.prob_up)),prob_up=p.prob_up,
        expected_low=p.expected_low,expected_high=p.expected_high,stop=p.invalidation,ref_price=p.ref_price,
        rank=p.rank,reason=p.rationale,sources=json.loads(p.sources),model=p.model_version,cutoff=p.data_cutoff,
        sample=p.synthetic,allocation=p.allocation,cost_rate=p.cost_rate,
        past_right=sum(bool(x[1].right) for x in earlier),past_total=len(earlier),
        result=('Pending' if not r else 'Flat' if r.right is None else 'Right' if r.right else 'Wrong'),
        entry=r.entry if r else None,exit=r.exit if r else None,pnl=round(r.pnl,2) if r and r.pnl is not None else None,
        baseline_pnl=round(r.baseline_pnl,2) if r and r.baseline_pnl is not None else None,
        cause=r.cause if r else None,explanation=r.explanation if r else None)

def summarize(rows):
    completed=[row for row in rows if row[1]]
    directional=[row for row in completed if row[1].right is not None]
    pnl=sum(r.pnl or 0 for p,r,i in completed)
    baseline=sum(r.baseline_pnl or 0 for p,r,i in completed)
    right=sum(bool(r.right) for p,r,i in directional)
    always=sum(r.exit>r.entry for p,r,i in directional)
    brier=sum((p.prob_up-(r.exit>r.entry))**2 for p,r,i in directional)/len(directional) if directional else None
    base_brier=sum((.53-(r.exit>r.entry))**2 for p,r,i in directional)/len(directional) if directional else None
    buckets=defaultdict(list)
    for row in completed:buckets[row[0].date].append(row)
    equity=[];total=base_total=peak=drawdown=0
    for day,values in sorted(buckets.items()):
        daily=sum(x[1].pnl or 0 for x in values);bdaily=sum(x[1].baseline_pnl or 0 for x in values)
        total+=daily;base_total+=bdaily;peak=max(peak,total);drawdown=max(drawdown,peak-total)
        valid=[x for x in values if x[1].right is not None]
        equity.append(dict(date=day,model=round(total,2),baseline=round(base_total,2),daily=round(daily,2),baseline_daily=round(bdaily,2),right=sum(bool(x[1].right) for x in valid),total=len(valid),funded=sum(x[1].pnl is not None for x in values)))
    return dict(pnl=round(pnl,2),baseline_pnl=round(baseline,2),difference=round(pnl-baseline,2),
        right=right,total=len(directional),pending=sum(row[1] is None for row in rows),
        accuracy=round(right/len(directional)*100,1) if directional else None,
        baseline_accuracy=round(always/len(directional)*100,1) if directional else None,
        brier=round(brier,4) if brier is not None else None,baseline_brier=round(base_brier,4) if base_brier is not None else None,
        costs=round(sum(r.costs for p,r,i in completed),2),days=len(equity),
        winning_days=sum(x['daily']>0 for x in equity),losing_days=sum(x['daily']<0 for x in equity),
        best_day=max((x['daily'] for x in equity),default=0),worst_day=min((x['daily'] for x in equity),default=0),
        max_drawdown=round(drawdown,2),equity=equity)

def dashboard(session,selected=None):
    allrows=records(session,before=selected)
    dates=sorted({p.date for p,r,i in allrows},reverse=True)
    current=selected or (dates[0] if dates else None)
    picks=[row for row in allrows if row[0].rank is not None]
    today=[row for row in picks if row[0].date==current]
    previous=next((d for d in dates if current and d<current and any(p.date==d and r for p,r,i in picks)),None)
    yesterday=[row for row in picks if row[0].date==previous]
    stats=summarize(picks)
    sample=any(p.synthetic for p,r,i in allrows)
    matched60=sorted({p.date for p,r,i in picks if r})[-60:]
    recent=summarize([x for x in picks if x[0].date in matched60])
    enough=len(matched60)>=60 and not sample
    honest=recent['brier'] is not None and recent['baseline_brier'] is not None and recent['brier']<recent['baseline_brier']
    # Passing Brier alone is not proof of calibration. F&O remains locked pending actual calibration and live validation.
    from .daily_status import call_status
    return dict(mode='demo' if sample else 'live',date=current,previous_date=previous,dates=dates,
        daily_status=call_status(session,current) if current and not sample else None,
        calls=[serialize(*row,allrows) for row in today],yesterday=[serialize(*row,allrows) for row in yesterday],
        today_summary=summarize(today),yesterday_summary=summarize(yesterday),summary=stats,
        verdict={'ready':False,'title':'A useful experiment. Still unproven.' if sample else 'Still gathering evidence.',
            'description':'These are generated examples. They show how the journal works, not how a model performs in the market.' if sample else 'Keep watching the results. A profitable strategy has not been established.',
            'checks':[{'label':'Right more often than simply buying','value':f"{recent['accuracy'] or 0}% vs {recent['baseline_accuracy'] or 0}%",'passed':enough and (recent['accuracy'] or 0)>(recent['baseline_accuracy'] or 0)},
              {'label':'Its confidence matches its results','value':'Not verified on live calls','passed':False},
              {'label':'Makes money after costs','value':f"{recent['days']} {'sample' if sample else 'recorded'} days",'passed':enough and recent['pnl']>0 and recent['difference']>0}],
            'fno_unlocked':False,'completed_days':len(matched60),'probability_score_better':honest},
        methodology={'allocation':1000,'cost_percent':.15,'horizon':'09:15 open → 15:30 close','cutoff':'07:00 IST','index_policy':'Direction scored; no money placed on indices. No proxy is assumed.','stop_policy':'Alert level only. Daily data cannot confirm a stop fill.','model':'Five-day trend rule. Probabilities are not yet calibrated.'})

def track_record(session):
    allrows=records(session);picks=[x for x in allrows if x[0].rank is not None]
    complete=[x for x in picks if x[1] and x[1].right is not None]
    months=defaultdict(list);groups=defaultdict(list);calibration=[]
    for row in [x for x in picks if x[1]]:
        months[row[0].date[:7]].append(row)
        groups['Buy calls' if row[0].direction=='UP' else 'Sell calls'].append(row)
        groups['Indices' if row[2].kind=='index' else 'Stocks'].append(row)
    for low,high in [(50,55),(55,60),(60,65),(65,70),(70,80),(80,101)]:
        bucket=[x for x in complete if low<=100*max(x[0].prob_up,1-x[0].prob_up)<high]
        if bucket:calibration.append(dict(label=f'{low}–{min(high,100)}%',expected=round(sum(100*max(x[0].prob_up,1-x[0].prob_up) for x in bucket)/len(bucket),1),actual=round(sum(bool(x[1].right) for x in bucket)/len(bucket)*100,1),count=len(bucket)))
    dates=sorted({p.date for p,r,i in complete});rolling=[]
    for j,day in enumerate(dates):
        days=set(dates[max(0,j-29):j+1]);s=summarize([x for x in complete if x[0].date in days])
        rolling.append(dict(date=day,model=s['accuracy'],baseline=s['baseline_accuracy'],days=len(days)))
    return dict(summary=summarize(picks),months=[dict(month=m,**summarize(rows)) for m,rows in sorted(months.items(),reverse=True)],
        groups=[dict(name=g,**summarize(rows)) for g,rows in groups.items()],calibration=calibration,rolling=rolling,
        causes=[dict(name='No confirmed cause' if cause=='MODEL_NOISE' else cause,count=count) for cause,count in Counter(r.cause for p,r,i in complete if r.right is False).items()])

def system_health(session):
    from datetime import datetime,timezone
    from .market import quote_snapshot
    from .news import news_snapshot
    versions=session.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    jobs=session.scalars(select(JobRun).order_by(JobRun.id.desc()).limit(20)).all()
    ideas=session.scalars(select(Improvement).order_by(Improvement.id)).all()
    data=dashboard(session)
    violations=0
    for p,r,i in records(session):
        if any(s.get('published_at','')>p.data_cutoff or s.get('ingested_at','')>p.data_cutoff for s in json.loads(p.sources)):violations+=1
    quarantined=len(session.scalars(select(RawRecord.id).where(RawRecord.status=='quarantined')).all())
    import os
    live=quote_snapshot(session)
    news=news_snapshot(session)
    worker_at=live['worker_at']
    worker_ok=bool(worker_at and (datetime.now(timezone.utc)-datetime.fromisoformat(worker_at)).total_seconds()<60)
    telegram_verified=session.get(Setting,'telegram_verified_at')
    verified_chat=session.get(Setting,'telegram_verified_chat_id')
    telegram_verified=telegram_verified and verified_chat and verified_chat.value==os.getenv('TELEGRAM_CHAT_ID')
    from .models import EventAssessment,EventOutcome
    notes=session.scalar(select(func.count(EventAssessment.id))) or 0
    measured=session.scalar(select(func.count(EventOutcome.assessment_id)).where(EventOutcome.horizon=='session')) or 0
    from .daily_status import call_status
    from .market import IST
    daily=call_status(session,datetime.now(IST).date().isoformat())
    return dict(mode=data['mode'],checks=[
        dict(name='Today’s calls',status='ok' if daily['status']=='ready' else 'warning',detail=daily['reason']),
        dict(name='Morning notification',status='ok' if daily['telegram']=='sent' else 'warning',detail='Telegram confirmed delivery' if daily['telegram']=='sent' else 'Delivery unconfirmed; inspect before retrying' if daily['telegram']=='unconfirmed' else 'No Telegram delivery attempted for today'),
        dict(name='Morning cutoff',status='ok' if violations==0 else 'bad',detail=f'{violations} recorded source-time violations'),
        dict(name='Price history',status='warning' if data['mode']=='demo' else 'ok' if data['date'] else 'warning',detail='Generated sample prices' if data['mode']=='demo' else 'Imported history; check the last date'),
        dict(name='Price checks',status='warning' if quarantined else 'ok',detail=f'{quarantined} rows held for review'),
        dict(name='Telegram',status='ok' if telegram_verified and os.getenv('TELEGRAM_ENABLED')=='true' else 'warning',detail='Sending disabled' if os.getenv('TELEGRAM_ENABLED')!='true' else 'Bot and private chat verified' if telegram_verified else 'Configured; run the connection check'),
        dict(name='Event notes',status='ok' if notes else 'warning',detail=f'{notes} notes · {measured} measured session reactions' if notes else 'No company news has been assessed yet'),
        dict(name='Scheduler',status='ok' if worker_ok else 'warning',detail=f'Last check: {worker_at}' if worker_at else 'Not running'),
        dict(name='Latest prices',status='ok' if any(not q['stale'] for q in live['quotes']) else 'warning',detail=f"{len(live['quotes'])} saved prices · {live['provider']} · checks every {live['refresh_seconds']} seconds" if live['quotes'] else 'Market-data connection not ready'),
        dict(name='News feeds',status='ok' if news['sources'] and all(x['status']=='ok' for x in news['sources']) else 'warning',detail='; '.join(x['source']+': '+x['status'] for x in news['sources']) or 'No feeds selected'),
        dict(name='Market hours',status='ok' if live['schedule_known'] else 'warning',detail='Session calendar loaded' if live['schedule_known'] else 'Unconfirmed; scheduled calls are paused')],
        models=[dict(name=x.name,status=x.status,description=x.description,date=x.created_at,brier=x.brier) for x in versions],
        jobs=[dict(name=x.job,status=x.status,rows=x.rows,detail=x.detail,at=x.started_at) for x in jobs],
        ideas=[dict(id=x.id,title=x.title,detail=x.detail,status=x.status) for x in ideas],
        agents=[dict(name=name,weight=0,status='Not connected') for name in ['Market reader','Company news reader','Chart reader','Call reviewer','Daily writer','Evening reviewer']],
        budget={'used':sum(x.reserved for x in session.scalars(select(TokenBudget).where(TokenBudget.date==data['date'])).all()),'cap':int(os.getenv('DAILY_TOKEN_CAP','12000'))},fno_unlocked=False)
