import csv,io,os,secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Depends,HTTPException,Request,BackgroundTasks
from fastapi.responses import Response,FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic,HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import analytics,briefs
from .config import MODE,ROOT
from .db import initialize,SessionLocal,session_dependency
from .demo import seed_demo
from .models import Improvement,Instrument,Price,Setting
from .market import quote_snapshot
from .news import news_snapshot
from .refresh import request_refresh, refresh_status, run_refresh, RefreshCooldown
from .market import MarketError,create_provider
from .events import EFFECTS,EVENT_TYPES,calendar_hours,event_notes,history_summary,note_payload,record_owner_assessment
from .models import NewsArticle
from .index_research import snapshot as index_snapshot
from .index_jobs import REFRESH_KEY as INDEX_REFRESH_KEY, run_index_refresh

FRONTEND_ORIGINS=[x.strip().rstrip('/') for x in os.getenv('FRONTEND_ORIGINS','').split(',') if x.strip()]
if '*' in FRONTEND_ORIGINS:raise ValueError('FRONTEND_ORIGINS must list exact origins, never a wildcard')

@asynccontextmanager
async def lifespan(app):
    initialize()
    with SessionLocal() as session:
        mode=session.get(Setting,'dataset_mode')
        if mode and mode.value!=MODE:raise RuntimeError('APP_MODE differs from database. Use a separate database for live data.')
        if MODE=='demo':seed_demo(session)
    yield

security=HTTPBasic(auto_error=False)
def owner(credentials:HTTPBasicCredentials|None=Depends(security)):
    password=os.getenv('OWNER_PASSWORD')
    if not password:
        if MODE=='live':raise HTTPException(503,'Set OWNER_PASSWORD before using live mode')
        return
    if not credentials or not (secrets.compare_digest(credentials.username,os.getenv('OWNER_USER','ravi')) and secrets.compare_digest(credentials.password,password)):
        raise HTTPException(401,'Private journal',headers={'WWW-Authenticate':'Basic'})

app=FastAPI(title='Nifty Signal',version='0.1.0',lifespan=lifespan,dependencies=[Depends(owner)])

@app.middleware('http')
async def browser_write_guard(request:Request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        allowed={f'{request.url.scheme}://{request.headers.get("host")}', 'http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:4173','http://localhost:4173',*FRONTEND_ORIGINS}
        if origin and origin not in allowed:return Response('Untrusted origin',status_code=403)
        if request.headers.get('content-type','').split(';')[0]!='application/json':return Response('Use application/json',status_code=415)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response

app.add_middleware(CORSMiddleware,allow_origins=FRONTEND_ORIGINS,
    allow_methods=['GET','POST'],allow_headers=['Authorization','Content-Type'],allow_credentials=False)

@app.get('/api/session')
def check_session():
    if not os.getenv('OWNER_PASSWORD'):raise HTTPException(503,'Configure the owner password on the backend before opening the hosted site')
    return {'signed_in':True}

@app.get('/api/quotes')
def quotes(session:Session=Depends(session_dependency)):
    return quote_snapshot(session)

@app.get('/api/indices')
def indices(session:Session=Depends(session_dependency)):
    result=index_snapshot(session)
    result['refresh']=refresh_status(session,key=INDEX_REFRESH_KEY)
    result['can_fetch']=MODE=='live'
    return result

@app.post('/api/indices/refresh',status_code=202)
def refresh_indices(background_tasks:BackgroundTasks,session:Session=Depends(session_dependency)):
    try:state,started=request_refresh(session,key=INDEX_REFRESH_KEY)
    except RefreshCooldown as error:
        raise HTTPException(429,str(error),headers={'Retry-After':str(error.seconds)}) from None
    except MarketError as error:raise HTTPException(409,str(error)) from None
    if started:background_tasks.add_task(run_index_refresh,state['id'])
    return state

@app.get('/api/indices/brief')
def index_brief(session:Session=Depends(session_dependency)):
    message=briefs.indices(index_snapshot(session))
    return dict(text=briefs.plain_text(message),html=message,parse_mode='HTML',sent=False)

@app.get('/api/news')
def news(session:Session=Depends(session_dependency)):
    return news_snapshot(session)

@app.get('/api/refresh')
def latest_fetch_status(session:Session=Depends(session_dependency)):
    return refresh_status(session)

@app.post('/api/refresh', status_code=202)
def fetch_latest(background_tasks:BackgroundTasks, session:Session=Depends(session_dependency)):
    try: state, started = request_refresh(session)
    except RefreshCooldown as error:
        raise HTTPException(429, str(error), headers={'Retry-After': str(error.seconds)}) from None
    except MarketError as error: raise HTTPException(409, str(error)) from None
    if started: background_tasks.add_task(run_refresh, state['id'])
    return state

@app.get('/api/today')
def today(date:str|None=None,session:Session=Depends(session_dependency)):
    return analytics.dashboard(session,date)

@app.get('/api/track-record')
def track(session:Session=Depends(session_dependency)):
    return analytics.track_record(session)

@app.get('/api/stocks')
def stocks(session:Session=Depends(session_dependency)):
    return [dict(symbol=i.symbol,name=i.name,sector=i.sector,kind=i.kind) for i in session.scalars(select(Instrument).order_by(Instrument.symbol))]

@app.get('/api/stocks/{symbol}')
def stock(symbol:str,session:Session=Depends(session_dependency)):
    instrument=session.get(Instrument,symbol)
    if not instrument:raise HTTPException(404,'Stock not found')
    rows=analytics.records(session,symbol=symbol)
    prices=session.scalars(select(Price).where(Price.symbol==symbol).order_by(Price.date)).all()
    return dict(symbol=symbol,name=instrument.name,sector=instrument.sector,summary=analytics.summarize(rows),
        calls=[analytics.serialize(*row,rows) for row in reversed(rows)],
        prices=[dict(date=p.date,close=p.close) for p in prices],mode='demo' if any(p.synthetic for p in prices) else 'live',
        events=event_notes(session,symbol),patterns=history_summary(session,symbol),
        event_options=dict(event_types=list(EVENT_TYPES),effects=list(EFFECTS)))

class OwnerAssessment(BaseModel):
    symbol:str
    event_type:str
    effect:str
    facts:str
    expectation:str|None=None
    confidence:str='medium'

@app.post('/api/events/{article_id}/assessment',status_code=201)
def assess(article_id:int,body:OwnerAssessment,session:Session=Depends(session_dependency)):
    """The owner's own read of an article. It is added as a new version; earlier notes stay as written."""
    if not session.get(NewsArticle,article_id):raise HTTPException(404,'Article not found')
    hours=None;provider=None
    try:
        provider=create_provider()
        hours=calendar_hours(session,provider)
    except MarketError:pass  # The note is still saved; its reaction window is shown as unknown.
    try:row=record_owner_assessment(session,article_id,body.symbol.strip().upper(),body.event_type,body.effect,body.facts,
        expectation=body.expectation,confidence=body.confidence,hours=hours)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    finally:
        if provider:provider.close()
    session.commit()
    article=session.get(NewsArticle,article_id)
    return dict(note=note_payload(session,row,article,row.assessed_at),message='Saved as a new note. No call or earlier note was changed.')

@app.get('/api/health')
def health(session:Session=Depends(session_dependency)):
    return analytics.system_health(session)

class Decision(BaseModel):
    decision:str

@app.post('/api/improvements/{idea_id}')
def decide(idea_id:int,body:Decision,session:Session=Depends(session_dependency)):
    if body.decision not in ('queued','skipped'):raise HTTPException(422,'Choose queued or skipped')
    idea=session.get(Improvement,idea_id)
    if not idea:raise HTTPException(404,'Idea not found')
    if idea.status!='pending':raise HTTPException(409,'This idea already has a decision')
    idea.status=body.decision;session.commit()
    return {'status':idea.status,'message':'Saved for a future experiment. No model was changed.' if idea.status=='queued' else 'Idea skipped.'}

@app.get('/api/brief/{period}')
def brief(period:str,date:str|None=None,session:Session=Depends(session_dependency)):
    if period not in ('morning','evening'):raise HTTPException(404,'Choose morning or evening')
    data=analytics.dashboard(session,date)
    message=getattr(briefs,period)(data)
    return dict(text=briefs.plain_text(message),html=message,parse_mode='HTML',sent=False)

@app.get('/api/export.csv')
def export(session:Session=Depends(session_dependency)):
    rows=analytics.records(session);out=io.StringIO();writer=csv.writer(out)
    writer.writerow(['date','symbol','direction','prob_up','entry','exit','result','paper_pnl','simply_buying','sample'])
    for p,r,i in rows:
        if p.rank is not None:writer.writerow([p.date,p.symbol,p.direction,p.prob_up,r.entry if r else '',r.exit if r else '',('Flat' if r.right is None else 'Right' if r.right else 'Wrong') if r else 'Pending',r.pnl if r else '',r.baseline_pnl if r else '',p.synthetic])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="nifty-signal-calls.csv"'})

dist=ROOT/'frontend'/'dist'
if (dist/'assets').exists():app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')

@app.get('/{path:path}',include_in_schema=False)
def frontend(path:str):
    if path.startswith('api/'):raise HTTPException(404,'API route not found')
    if path=='mark.svg' and (dist/'mark.svg').exists():return FileResponse(dist/'mark.svg')
    if (dist/'index.html').exists():return FileResponse(dist/'index.html')
    raise HTTPException(404,'Build the frontend or run Vite on port 5173')
