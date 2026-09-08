"""Bounded public RSS collection. News is evidence, not an automatic buy/sell signal."""
import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, select

from .engine import utcstamp
from .ingest import import_news, now
from .market import IST, MarketError
from .models import Evidence, Instrument, NewsArticle, Setting

FEEDS = {
    'et-markets': ('ET Markets', 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms'),
    'mint-markets': ('LiveMint Markets', 'https://www.livemint.com/rss/markets'),
    'mint-companies': ('LiveMint Companies', 'https://www.livemint.com/rss/companies'),
    'rbi': ('RBI', 'https://www.rbi.org.in/pressreleases_rss.xml'),
    'nse': ('NSE announcements', 'https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml'),
    'moneycontrol': ('Moneycontrol', 'https://www.moneycontrol.com/rss/latestnews.xml'),
}
DEFAULT_FEEDS = 'et-markets,mint-markets,mint-companies,rbi'
MAX_BYTES = 2_000_000

def configured_feeds():
    names = list(dict.fromkeys(x.strip() for x in os.getenv('NEWS_FEEDS', DEFAULT_FEEDS).split(',') if x.strip()))
    if any(x not in FEEDS for x in names): raise MarketError('NEWS_FEEDS contains an unsupported source name.')
    return names

def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value or ''))).strip()

def parse_feed(content, source, received):
    if len(content) > MAX_BYTES or b'\x00' in content or b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
        raise MarketError('News feed exceeded the size limit or used unsupported XML declarations.')
    try: root = ET.fromstring(content)
    except ET.ParseError: raise MarketError('The news source did not return a valid RSS or Atom feed.') from None
    if root.tag.rsplit('}', 1)[-1] not in ('rss', 'feed', 'RDF'):
        raise MarketError('The news source returned a page instead of a feed.')
    items, invalid = [], 0
    for node in [x for x in root.iter() if x.tag.rsplit('}', 1)[-1] in ('item', 'entry')][:200]:
        fields = {x.tag.rsplit('}', 1)[-1]: x for x in node}
        def value(key):
            el = fields.get(key)
            return ''.join(el.itertext()) if el is not None else ''
        try:
            title = plain(value('title'))[:500]
            url = value('link').strip()
            if not url and 'link' in fields: url = fields['link'].get('href', '')
            parts = urlsplit(url)
            if not title or parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
                raise ValueError()
            raw_time = value('pubDate') or value('published') or value('date') or value('updated')
            try: stamp = parsedate_to_datetime(raw_time)
            except (ValueError, TypeError): stamp = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
            basis = 'source timezone'
            if stamp.tzinfo is None:
                # RBI's observed RSS dates omit the zone. Store this explicit assumption;
                # actual receipt is independently enforced at the prediction boundary.
                if source != 'rbi': raise ValueError()
                stamp = stamp.replace(tzinfo=IST); basis = 'RBI time interpreted as IST'
            published = utcstamp(stamp.isoformat())
            if published > received: raise ValueError()
            items.append(dict(title=title, url=url.split('#')[0], body=plain(value('description') or value('summary'))[:2000],
                published_at=published, time_basis=basis))
        except (ValueError, TypeError, OverflowError): invalid += 1
    return items, invalid

def company_matches(title, instruments):
    normalized = ' ' + re.sub(r'[^a-z0-9]+', ' ', title.lower()).strip() + ' '
    matched = []
    for instrument in instruments:
        if instrument.kind != 'stock': continue
        name = re.sub(r'\s+(limited|ltd)\.?$', '', instrument.name.lower()).strip()
        name = re.sub(r'[^a-z0-9]+', ' ', name).strip()
        # Full company-name matching only; short common-word tickers are ambiguous.
        if len(name) >= 6 and f' {name} ' in normalized: matched.append(instrument.symbol)
    return matched

def collect_news(session, sources=None, transport=None, observed_at=None):
    mode = session.get(Setting, 'dataset_mode')
    if mode and mode.value != 'live': raise MarketError('Public news requires a separate live database.')
    sources = configured_feeds() if sources is None else sources
    instruments = session.scalars(select(Instrument)).all()
    results = []
    with httpx.Client(timeout=15, transport=transport, follow_redirects=False) as client:
        for source in sources:
            if source not in FEEDS: raise MarketError('Unknown public news source.')
            name, url = FEEDS[source]
            result = dict(source=name, checked_at=utcstamp(observed_at or now()), status='unavailable',
                added=0, duplicate=0, old=0, invalid=0, latest_published_at=None)
            try:
                with client.stream('GET', url, headers={'Accept': 'application/rss+xml, application/xml, text/xml'}) as response:
                    if response.status_code != 200: raise MarketError(f'Feed returned HTTP {response.status_code}.')
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_BYTES: raise MarketError('News feed exceeded the size limit.')
                received = utcstamp(observed_at or now())
                result['checked_at'] = received
                items, result['invalid'] = parse_feed(bytes(content), source, received)
                result['latest_published_at'] = max((x['published_at'] for x in items), default=None)
                oldest = (datetime.fromisoformat(received) - timedelta(days=14)).isoformat(timespec='seconds')
                for item in items:
                    if item['published_at'] < oldest: result['old'] += 1; continue
                    digest = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
                    if session.scalar(select(NewsArticle.id).where(NewsArticle.url == item['url'], NewsArticle.content_hash == digest)):
                        result['duplicate'] += 1; continue
                    symbols = company_matches(item['title'], instruments)
                    session.add(NewsArticle(source=name, content_hash=digest, received_at=received,
                        symbols=json.dumps(symbols), **item))
                    # Existing forecast evidence stays frozen at its first observed revision.
                    if len(symbols) == 1 and not session.scalar(select(Evidence.id).where(Evidence.url == item['url'])):
                        import_news(session, [dict(item, symbol=symbols[0])], received)
                    session.flush(); result['added'] += 1
                age = (datetime.fromisoformat(received) - datetime.fromisoformat(result['latest_published_at'])).total_seconds() if items else None
                result['status'] = 'ok' if age is not None and age <= 72 * 3600 else 'stale'
                result['detail'] = 'Collection only; stock impact has not been assessed.' if result['status'] == 'ok' else 'No recent dated articles were returned.'
            except (httpx.HTTPError, MarketError) as error:
                result['detail'] = str(error) if isinstance(error, MarketError) else 'News request failed; previous articles are kept.'
            key = 'news-source:' + source
            saved = session.get(Setting, key)
            if saved: saved.value = json.dumps(result)
            else: session.add(Setting(key=key, value=json.dumps(result)))
            results.append(result)
    session.flush()
    return results

def impact_label(labels):
    if not labels: return 'Not assessed'
    effects = sorted({x['effect'] for x in labels})
    return ' / '.join(effects) + (' · owner read' if any(x['assessor'] == 'owner' for x in labels) else ' · keyword rule')

def news_snapshot(session):
    from .events import article_labels
    # Latest observed revision per URL; earlier revisions remain in storage.
    latest = select(func.max(NewsArticle.id)).group_by(NewsArticle.url)
    articles = session.scalars(select(NewsArticle).where(NewsArticle.id.in_(latest)).order_by(NewsArticle.published_at.desc()).limit(30)).all()
    labels = article_labels(session, [x.id for x in articles])
    current = datetime.now(timezone.utc)
    sources = []
    for key in configured_feeds():
        saved = session.get(Setting, 'news-source:' + key)
        source = json.loads(saved.value) if saved else dict(source=FEEDS[key][0], status='unavailable', detail='Not collected yet.')
        if saved and (current - datetime.fromisoformat(source['checked_at'])).total_seconds() > 1800:
            source = {**source, 'status': 'stale', 'detail': 'Collection has not run in the last 30 minutes.'}
        sources.append(source)
    return dict(sources=sources, refresh_seconds=300, influences_predictions=False,
        articles=[dict(id=x.id, source=x.source, title=x.title, url=x.url, published_at=x.published_at,
            received_at=x.received_at, time_basis=x.time_basis, symbols=json.loads(x.symbols),
            impact=impact_label(labels.get(x.id)), assessments=labels.get(x.id, []),
            stale=(current - datetime.fromisoformat(x.published_at)).total_seconds() > 72 * 3600) for x in articles])
