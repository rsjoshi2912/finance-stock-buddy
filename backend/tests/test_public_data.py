import json
from datetime import datetime
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import market, scheduler
from app.db import build_engine, initialize
from app.engine import feature_evidence, cutoff_for
from app.models import Instrument, NewsArticle, Quote, Setting
from app.news import collect_news, parse_feed, company_matches
from app.public_data import YFinance, yahoo_symbol

def stock(session):
    session.add(Instrument(symbol='ABC', name='ABC Industries Limited', sector='Test', kind='stock', member_from='2026-01-01'))
    session.flush()

class Ticker:
    def __init__(self):
        self.calls = []
        self.meta = {'symbol': 'ABC.NS', 'currency': 'INR', 'exchangeTimezoneName': 'Asia/Kolkata',
            'regularMarketTime': pd.Timestamp('2026-09-07T10:00:00+05:30'), 'regularMarketPrice': 105.0}
    def history(self, **kwargs):
        self.calls.append(kwargs)
        return pd.DataFrame({'Open': [100., 104.], 'High': [103., 106.], 'Low': [99., 103.],
            'Close': [102., 105.], 'Volume': [1000, 2000]},
            index=pd.to_datetime(['2026-09-04', '2026-09-07']).tz_localize('Asia/Kolkata'))
    def get_history_metadata(self): return self.meta

def test_yahoo_keeps_provider_ohlc_and_requests_inclusive_end():
    ticker = Ticker(); provider = YFinance(ticker_factory=lambda _: ticker)
    bars = provider.candles('ABC.NS', '2026-09-04', '2026-09-07')
    assert ticker.calls[0]['end'] == '2026-09-08'
    assert ticker.calls[0]['auto_adjust'] is False and ticker.calls[0]['repair'] is False
    assert bars[0][1:5] == [100, 103, 99, 102]
    ticker.meta['currency'] = 'USD'
    with pytest.raises(market.MarketError, match='currency'): provider.candles('ABC.NS', '2026-09-04', '2026-09-07')

def test_yahoo_quotes_use_market_time_and_previous_session_close(session):
    stock(session); ticker = Ticker(); provider = YFinance(ticker_factory=lambda _: ticker)
    assert market.refresh_quotes(session, provider, '2026-09-07T05:00:00+00:00') == 1
    quote = session.get(Quote, 'ABC')
    assert quote.change == 3 and quote.provider == 'Yahoo Finance'
    assert quote.market_at == '2026-09-07T04:30:00+00:00'
    ticker.meta['regularMarketTime'] = pd.Timestamp('2026-09-04T15:30:00+05:30')
    with pytest.raises(market.MarketError): market.refresh_quotes(session, provider, '2026-09-07T05:01:00+00:00')
    assert quote.market_at == '2026-09-07T04:30:00+00:00'

def test_yahoo_failure_is_controlled_and_not_relabelled_as_a_price():
    def failing(_): raise RuntimeError('private cookie or remote error body')
    with pytest.raises(market.MarketError) as error: YFinance(ticker_factory=failing).quotes(['ABC.NS'])
    assert 'cookie' not in str(error.value)

def test_provider_switch_does_not_require_a_broker_token(session, monkeypatch):
    monkeypatch.delenv('UPSTOX_ACCESS_TOKEN', raising=False)
    monkeypatch.setenv('MARKET_DATA_PROVIDER', 'yfinance')
    assert market.create_provider().id == 'yfinance'
    monkeypatch.setenv('MARKET_DATA_PROVIDER', 'upstox')
    with pytest.raises(market.MarketError, match='UPSTOX_ACCESS_TOKEN'): market.create_provider()
    from app.live import doctor
    stock(session)
    assert doctor(session)['configuration_ready'] is False
    assert doctor(session)['mapped_instruments'] == 0

def test_indian_mapping_does_not_guess_unknown_indices():
    assert yahoo_symbol(SimpleNamespace(symbol='M&M', kind='stock')) == 'M&M.NS'
    assert yahoo_symbol(SimpleNamespace(symbol='BANKNIFTY', kind='index')) == '^NSEBANK'
    with pytest.raises(market.MarketError): yahoo_symbol(SimpleNamespace(symbol='UNKNOWN', kind='index'))

def test_public_calendar_fails_closed_and_honours_special_sessions(tmp_path):
    path = tmp_path / 'calendar.json'; provider = YFinance(ticker_factory=Ticker, calendar_path=path)
    with pytest.raises(market.MarketError, match='verified'): provider.timings('2026-09-07')
    path.write_text(json.dumps({'2026': ['2026-09-14'], 'sessions': {'2026-11-08': {'open': '18:00', 'close': '19:00'}}}))
    assert provider.timings('2026-09-14') == []
    assert provider.timings('2026-09-12') == []
    assert provider.timings('2026-11-08')[0]['start_time'].endswith('18:00:00+05:30')
    with pytest.raises(market.MarketError): provider.timings('2027-01-04')

def test_bundled_calendar_covers_published_amendments():
    from app.config import ROOT
    provider = YFinance(ticker_factory=Ticker, calendar_path=ROOT / 'backend/data/nse-calendar-2026.json')
    assert provider.timings('2026-01-15') == []
    assert provider.timings('2026-02-01')[0]['start_time'].endswith('09:15:00+05:30')
    assert provider.timings('2026-09-07')
    with pytest.raises(market.MarketError): provider.timings('2026-11-08')

def rss(title='ABC Industries wins a contract', published='Mon, 07 Sep 2026 06:40:00 +0530'):
    return f'<rss><channel><item><title>{title}</title><link>https://publisher.example/a</link><pubDate>{published}</pubDate><description>Source excerpt</description></item></channel></rss>'.encode()

def test_public_news_keeps_receipt_and_revisions_without_rewriting_forecast_evidence(session):
    stock(session)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=rss()))
    first = collect_news(session, ['et-markets'], transport, '2026-09-07T01:29:00+00:00')
    assert first[0]['added'] == 1
    second = collect_news(session, ['et-markets'], transport, '2026-09-07T01:31:00+00:00')
    assert second[0]['duplicate'] == 1
    changed = httpx.MockTransport(lambda _: httpx.Response(200, content=rss('ABC Industries cancels a contract')))
    collect_news(session, ['et-markets'], changed, '2026-09-07T01:32:00+00:00')
    assert len(session.scalars(select(NewsArticle)).all()) == 2
    evidence = feature_evidence(session, 'ABC', cutoff=cutoff_for('2026-09-07'))
    assert len(evidence) == 1 and 'wins' in evidence[0].title
    assert evidence[0].ingested_at == '2026-09-07T01:29:00+00:00'

def test_late_old_news_never_enters_an_earlier_forecast(session):
    stock(session)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=rss()))
    collect_news(session, ['et-markets'], transport, '2026-09-07T01:31:00+00:00')
    assert feature_evidence(session, 'ABC', cutoff=cutoff_for('2026-09-07')) == []

def test_successful_http_with_old_news_is_stale_and_one_failed_feed_does_not_block_others(session):
    def respond(request):
        if 'moneycontrol' in request.url.host: return httpx.Response(200, content=rss(published='Tue, 23 Apr 2024 13:41:02 +0530'))
        if 'nseindia' in request.url.host: return httpx.Response(403)
        return httpx.Response(200, content=rss())
    result = collect_news(session, ['moneycontrol', 'nse', 'et-markets'], httpx.MockTransport(respond), '2026-09-07T01:29:00+00:00')
    assert [x['status'] for x in result] == ['stale', 'unavailable', 'ok']
    assert result[0]['old'] == 1 and result[2]['added'] == 1

def test_feed_rejects_unsafe_xml_future_and_unknown_timezone():
    received = '2026-09-07T01:29:00+00:00'
    with pytest.raises(market.MarketError): parse_feed(b'<!DOCTYPE rss [<!ENTITY x "value">]><rss/>', 'et-markets', received)
    assert parse_feed(rss(published='Mon, 07 Sep 2026 08:00:00 +0530'), 'et-markets', received)[1] == 1
    assert parse_feed(rss(published='Mon, 07 Sep 2026 06:40:00'), 'et-markets', received)[1] == 1
    items, invalid = parse_feed(rss(published='Mon, 07 Sep 2026 06:40:00'), 'rbi', received)
    assert not invalid and items[0]['time_basis'] == 'RBI time interpreted as IST'

def test_matching_does_not_assign_a_common_word_ticker():
    company = SimpleNamespace(symbol='IDEA', name='Vodafone Idea Limited', kind='stock')
    assert company_matches('An investment idea for this week', [company]) == []
    assert company_matches('Vodafone Idea reports results', [company]) == ['IDEA']

def test_scheduler_collects_public_data_without_fabricating_unknown_market_sessions(tmp_path, monkeypatch):
    engine = build_engine(f'sqlite:///{tmp_path}/schedule.db'); initialize(engine)
    factory = lambda: Session(engine, expire_on_commit=False)
    monkeypatch.setattr(scheduler, 'MODE', 'live'); monkeypatch.setenv('OWNER_PASSWORD', 'fixture-only')
    monkeypatch.setenv('NEWS_ENABLED', 'true')
    monkeypatch.setattr(scheduler, 'market_session', lambda *_: (_ for _ in ()).throw(market.MarketError('No calendar')))
    calls = []
    monkeypatch.setattr(scheduler, 'collect_news', lambda _: calls.append('news'))
    monkeypatch.setattr(scheduler, 'refresh_quotes', lambda *_: calls.append('quotes'))
    provider = SimpleNamespace(id='yfinance', refresh_seconds=300)
    for at in ('07:30:00', '07:30:30', '10:00:00', '10:00:30'):
        jobs = scheduler.tick(provider, datetime.fromisoformat('2026-09-07T'+at+'+05:30'), factory)
        assert 'predict' not in jobs and 'morning' not in jobs
    assert calls.count('news') == 2 and calls.count('quotes') == 1
    engine.dispose()
