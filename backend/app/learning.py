"""Optional LightGBM walk-forward research. No automatic deployment of untested output."""
import json
from pathlib import Path
from statistics import mean,stdev
from sqlalchemy import select
from .engine import feature_prices,feature_evidence,cutoff_for
from .models import Prediction,Resolution

FEATURE_NAMES=['return_1d','return_5d','return_20d','volatility_20d','volume_vs_average','news_sentiment']

def features_for(session,symbol,cutoff):
    prices=feature_prices(session,symbol,cutoff=cutoff,limit=30)
    if len(prices)<21:return None
    c=[p.close for p in prices];ret=[b/a-1 for a,b in zip(c,c[1:])]
    evidence=feature_evidence(session,symbol,cutoff=cutoff)
    avg_volume=mean(p.volume for p in prices)
    return [c[-1]/c[-2]-1,c[-1]/c[-6]-1,c[-1]/c[-21]-1,stdev(ret[-20:]),
            prices[-1].volume/avg_volume if avg_volume else 0,
            mean(e.sentiment for e in evidence) if evidence else 0]

def training_rows(session,asof,allow_sample=False):
    rows=[]
    query=select(Prediction,Resolution).join(Resolution,Resolution.prediction_id==Prediction.id).where(
        Prediction.model_version=='momentum_research_v1',Resolution.resolved_at<=asof)
    for p,r in session.execute(query.order_by(Prediction.date,Prediction.symbol)):
        if p.synthetic and not allow_sample:continue
        if r.exit==r.entry:continue
        features=features_for(session,p.symbol,p.data_cutoff)
        if features is None:continue
        rows.append(dict(key=f'{p.date}:{p.symbol}',date=p.date,features=features,outcome=int(r.exit>r.entry),
            label_available_at=r.resolved_at,champion_probability=p.prob_up,sample=p.synthetic))
    return rows

def walk_forward(rows,min_train_days=40,evaluation_days=60):
    """Train only on earlier dates, holding out whole sessions across every stock."""
    from lightgbm import LGBMClassifier
    dates=sorted({x['date'] for x in rows})
    if len(dates)<min_train_days+evaluation_days:
        raise ValueError(f'Need at least {min_train_days+evaluation_days} resolved days; found {len(dates)}')
    results=[]
    for day in dates[-evaluation_days:]:
        train=[r for r in rows if r['date']<day and r['label_available_at']<=cutoff_for(day)]
        test=[r for r in rows if r['date']==day]
        if len({r['outcome'] for r in train})<2:raise ValueError('Training needs both directions')
        model=LGBMClassifier(n_estimators=80,max_depth=3,num_leaves=7,learning_rate=.04,min_child_samples=40,random_state=17,n_jobs=2,verbosity=-1)
        model.fit([r['features'] for r in train],[r['outcome'] for r in train])
        probabilities=model.predict_proba([r['features'] for r in test])[:,1]
        for row,p in zip(test,probabilities):results.append({k:v for k,v in row.items() if k!='features'}|{'prob_up':float(p),'out_of_sample':True})
    return results

def save_research_report(rows,path):
    results=walk_forward(rows)
    brier=mean((r['prob_up']-r['outcome'])**2 for r in results)
    champion=mean((r['champion_probability']-r['outcome'])**2 for r in results)
    report={'model':'LightGBM research v1','evaluation_days':len({r['date'] for r in results}),
        'brier':brier,'champion_brier':champion,'beats_champion':brier<champion,
        'contains_sample_data':any(r['sample'] for r in results),'promoted':False,
        'note':'Research report only. Probability calibration, cost-based selection, and live validation are still required.',
        'features':FEATURE_NAMES,'predictions':results}
    Path(path).write_text(json.dumps(report,indent=2))
    return report

def finbert_sentiment(texts):
    """Optional CPU model. Downloads weights only when explicitly invoked."""
    from transformers import pipeline
    sentiment=pipeline('text-classification',model='ProsusAI/finbert',device=-1,truncation=True,max_length=512)
    scores=[]
    for item in sentiment([t[:2000] for t in texts],batch_size=8):
        scores.append(item['score']*(1 if item['label']=='positive' else -1 if item['label']=='negative' else 0))
    return scores
