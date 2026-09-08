"""Explicit CLI jobs. No sending, cloud provisioning, or broker orders during setup."""
import argparse,json,os
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
from sqlalchemy import select,update
from .config import MODE,ROOT
from .db import initialize,SessionLocal
from .models import JobRun,TokenBudget,Setting
from .engine import make_daily_calls,resolve_day
from .analytics import dashboard
from .briefs import morning,evening,validate
from .ingest import import_instruments,import_prices,import_news,now

def trading_day(day,calendar):
    """Require a year-specific verified holiday file; never silently assume weekday = session."""
    d=date.fromisoformat(day)
    if str(d.year) not in calendar:raise ValueError(f'No verified NSE calendar loaded for {d.year}')
    return d.weekday()<5 and day not in calendar[str(d.year)]

def reserve_tokens(session,day,tokens,cap):
    if tokens<0 or cap<0:raise ValueError('Token counts must be non-negative')
    if not session.get(TokenBudget,day):
        session.add(TokenBudget(date=day,reserved=0));session.flush()
    result=session.execute(update(TokenBudget).where(TokenBudget.date==day,TokenBudget.reserved+tokens<=cap).values(reserved=TokenBudget.reserved+tokens))
    return result.rowcount==1

def send_telegram(text,period,day,session):
    if MODE!='live' or os.getenv('TELEGRAM_ENABLED')!='true':raise ValueError('Telegram is disabled. Live mode and explicit enablement are required.')
    validate(text)
    token=os.getenv('TELEGRAM_BOT_TOKEN');chat=os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:raise ValueError('Telegram token and the one allowed chat ID are required')
    verified=session.get(Setting,'telegram_verified_chat_id')
    if not verified or verified.value!=chat:raise ValueError('Run app.live telegram-check for this private chat before sending')
    key=f'telegram:{period}:{day}'
    existing=session.get(Setting,key)
    if existing:raise ValueError('This message was already attempted; inspect delivery before retrying manually')
    # Claim before network I/O. Ambiguous failures never cause automatic duplicate sends.
    session.add(Setting(key=key,value='attempted'));session.commit()
    try:
        with httpx.Client(timeout=20) as client:
            response=client.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat,'text':text,'parse_mode':'HTML','link_preview_options':{'is_disabled':True}})
            if response.status_code!=200 or not response.json().get('ok'):raise ValueError('Telegram rejected the delivery; inspect bot configuration')
    except httpx.HTTPError:
        # Never include the request URL; it contains the bot secret.
        raise ValueError('Telegram delivery could not be confirmed') from None
    session.get(Setting,key).value='sent';session.commit()

def main():
    parser=argparse.ArgumentParser(description='Nifty Signal local jobs')
    parser.add_argument('job',choices=['init','import-universe','import-prices','import-news','predict','resolve','brief','send'])
    parser.add_argument('--date',default=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat())
    parser.add_argument('--file');parser.add_argument('--source',default='owner supplied CSV')
    parser.add_argument('--period',choices=['morning','evening'],default='morning')
    args=parser.parse_args();initialize()
    with SessionLocal() as session:
        if args.job=='init':print('Database ready');return
        if args.job.startswith('import-'):
            if MODE!='live':raise ValueError('Imports require APP_MODE=live and a separate database')
            if not args.file:raise ValueError('--file is required')
            content=Path(args.file).read_text()
            if args.job=='import-universe':result=import_instruments(session,content)
            elif args.job=='import-prices':result=import_prices(session,content,args.source)
            else:result=import_news(session,json.loads(content))
        elif args.job=='predict':
            if MODE!='live':raise ValueError('The demo is frozen; live forecasts require a separate live database')
            calendar_file=ROOT/'data'/'nse-holidays.json'
            if not calendar_file.exists():raise ValueError('Load a verified data/nse-holidays.json before scheduling live forecasts')
            if not trading_day(args.date,json.loads(calendar_file.read_text())):print('Not an NSE trading day');return
            current=datetime.now(ZoneInfo('Asia/Kolkata'))
            if args.date!=current.date().isoformat() or current.hour>=9:
                raise ValueError('Live calls must be written on their date before 09:00 IST; backdated calls are prohibited')
            mode=session.get(Setting,'dataset_mode')
            if mode and mode.value!='live':raise ValueError('Refusing to forecast using a sample database')
            result=make_daily_calls(session,args.date)
        elif args.job=='resolve':result=resolve_day(session,args.date)
        else:
            data=dashboard(session,args.date);message=(morning if args.period=='morning' else evening)(data)
            if args.job=='send':send_telegram(message,args.period,args.date,session);result='Sent to the configured owner'
            else:print(message);return
        session.add(JobRun(job=args.job,status='ok',rows=result if isinstance(result,int) else 0,detail=str(result),started_at=now()))
        session.commit();print(result)

if __name__=='__main__':main()
