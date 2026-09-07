"""Small explicit import boundary. Raw input is retained; suspect rows are quarantined."""
import csv,io,json,math
from datetime import datetime,timezone
from difflib import SequenceMatcher
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy import select
from .engine import utcstamp
from .models import Evidence,Instrument,JobRun,Price,RawRecord,Setting

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')

def import_instruments(session,content):
    count=0
    for row in csv.DictReader(io.StringIO(content)):
        symbol=row['symbol'].strip().upper()
        if not symbol or len(symbol)>30:raise ValueError('Invalid instrument symbol')
        if session.get(Instrument,symbol):continue
        kind=row.get('kind','stock')
        if kind not in ('stock','index'):raise ValueError('Instrument kind must be stock or index')
        session.add(Instrument(symbol=symbol,name=row['name'],sector=row['sector'],kind=kind,
            member_from=row['member_from'],member_to=row.get('member_to') or None))
        count+=1
    session.flush()
    return count

def import_prices(session,content,source,received_at=None):
    received=utcstamp(received_at or now());mode=session.get(Setting,'dataset_mode')
    if mode and mode.value=='demo':raise ValueError('Use a separate live database; sample history cannot be mixed with imported prices')
    if not mode:session.add(Setting(key='dataset_mode',value='live'))
    counts={'accepted':0,'quarantined':0,'duplicate':0}
    for row in csv.DictReader(io.StringIO(content)):
        raw=RawRecord(source=source,payload=json.dumps(row),received_at=received,status='received')
        session.add(raw)
        try:
            symbol=row['symbol'].strip().upper();day=row['date'];datetime.strptime(day,'%Y-%m-%d')
            if not session.get(Instrument,symbol):raise ValueError('Instrument is missing from the supplied historical universe')
            if session.scalar(select(Price.id).where(Price.symbol==symbol,Price.date==day)):
                raw.status='duplicate';counts['duplicate']+=1;continue
            prices={k:float(row[k]) for k in ('open','high','low','close')}
            if not all(math.isfinite(v) and v>0 for v in prices.values()):raise ValueError('Prices must be finite and positive')
            if not prices['low']<=min(prices['open'],prices['close'])<=max(prices['open'],prices['close'])<=prices['high']:raise ValueError('Inconsistent daily high or low')
            volume=int(row['volume'])
            if volume<0:raise ValueError('Negative volume')
            stamp=utcstamp(row['published_at'])
            if stamp>received:raise ValueError('Publication is after receipt')
            if stamp<utcstamp(f'{day}T15:30:00+05:30'):raise ValueError('Daily close cannot be published before the close')
            previous=session.scalar(select(Price).where(Price.symbol==symbol,Price.date<day).order_by(Price.date.desc()).limit(1))
            if previous and abs(prices['close']/previous.close-1)>.25:
                # A verified corporate-action import is required; a self-declared flag is not accepted.
                raise ValueError('Move exceeds 25%; verify the corporate action and adjusted history before import')
            session.add(Price(symbol=symbol,date=day,**prices,volume=volume,published_at=stamp,ingested_at=received,source=source,synthetic=False))
            raw.status='accepted';counts['accepted']+=1
            session.flush()
        except (ValueError,KeyError,TypeError) as error:
            raw.status='quarantined';raw.reason=str(error);counts['quarantined']+=1
    session.add(JobRun(job='import prices',status='warning' if counts['quarantined'] else 'ok',rows=counts['accepted'],detail=json.dumps(counts),started_at=received))
    session.flush()
    return counts

def import_news(session,items,received_at=None):
    received=utcstamp(received_at or now());count=0
    recent=session.scalars(select(Evidence).order_by(Evidence.id.desc()).limit(1000)).all()
    for item in items:
        parts=urlsplit(item['url'])
        if parts.scheme not in ('http','https'):raise ValueError('News sources must have an HTTP(S) URL')
        url=urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))
        title=item['title'].strip()
        if not title:continue
        if any(x.url==url or SequenceMatcher(None,x.title.lower(),title.lower()).ratio()>.92 for x in recent):continue
        published=utcstamp(item['published_at'])
        if published>received:raise ValueError('News publication is after receipt')
        record=Evidence(symbol=item.get('symbol'),title=title,url=url,body=item.get('body','')[:2000],published_at=published,ingested_at=received,sentiment=0)
        session.add(record);recent.append(record);count+=1
    session.flush()
    return count
