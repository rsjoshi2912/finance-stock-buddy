import hashlib
import inspect
import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app import engine as engine_module, scheduler
from app.db import session_dependency
from app.demo import seed_demo
from app.engine import utcstamp
from app.events import (assess_new_articles, classify, comparable_events, eligible_session, event_notes,
    history_summary, record_outcomes)
from app.market import MarketError
from app.models import EventAssessment, EventOutcome, Instrument, NewsArticle, Price
from app.news import company_matches

HOLIDAYS = set()

def hours(day):
    d = date.fromisoformat(day)
    if d.weekday() >= 5 or day in HOLIDAYS: return {'date': day, 'open': None, 'close': None}
    return {'date': day, 'open': f'{day}T09:15:00+05:30', 'close': f'{day}T15:30:00+05:30'}

def stock(session, symbol='ABC', name='ABC Industries Limited', sector='Test'):
    session.add(Instrument(symbol=symbol, name=name, sector=sector, kind='stock', member_from='2026-01-01')); session.flush()

def article(session, title, published, received=None, symbols=('ABC',), url=None, body='', source='ET Markets'):
    row = NewsArticle(source=source, url=url or f'https://publisher.example/{hashlib.md5(title.encode()).hexdigest()[:8]}',
        title=title, body=body, content_hash=hashlib.sha256(title.encode()).hexdigest(), published_at=utcstamp(published),
        received_at=utcstamp(received or published), time_basis='source timezone', symbols=json.dumps(list(symbols)))
    session.add(row); session.flush(); return row

def bar(session, symbol, day, open_, close, ingested=None):
    session.add(Price(symbol=symbol, date=day, open=open_, high=max(open_, close), low=min(open_, close), close=close, volume=1000,
        published_at=utcstamp(f'{day}T16:00:00+05:30'), ingested_at=utcstamp(ingested or f'{day}T18:35:00+05:30'),
        source='fixture', synthetic=False)); session.flush()

def past_event(session, symbol, day, session_pct, gap_pct, available, effect='Positive', event_type='order_contract', copies=1):
    """A completed earlier event, inserted directly: article, frozen assessment and its recorded session reaction."""
    previous = (date.fromisoformat(day).toordinal() - 1)
    published = f'{date.fromordinal(previous).isoformat()}T17:00:00+05:30'
    for copy in range(copies):
        row = article(session, f'{symbol} story {day} copy {copy}', published, symbols=(symbol,))
        assessment = EventAssessment(article_id=row.id, symbol=symbol, event_type=event_type, effect=effect, horizon='next_session',
            confidence='low', facts='fixture', assessor='rules_v1', evidence_hash=row.content_hash, eligible_session=day,
            published_during_session=False, assessed_at=utcstamp(published))
        session.add(assessment); session.flush()
        session.add(EventOutcome(assessment_id=assessment.id, horizon='session', start_date=day, end_date=day, reference_close=100,
            open=100 + gap_pct, close=(100 + gap_pct) * (1 + session_pct / 100), gap_pct=gap_pct, session_pct=session_pct,
            change_pct=gap_pct + session_pct, bars_available_at=utcstamp(available), recorded_at=utcstamp(available)))
    session.flush()

def test_rules_are_conservative_and_never_judge_a_number_without_its_expectation():
    assert classify('ABC Industries wins a ₹500 crore order from NHAI')[:2] == ('order_contract', 'Positive')
    assert classify('ABC Industries cancels supply contract')[:2] == ('order_contract', 'Negative')
    event_type, effect, found = classify('ABC Industries Q2 net profit rises 20%')
    assert (event_type, effect) == ('earnings', 'Unclear') and 'expectation' in found['note']
    assert classify('ABC Industries profit falls 30% in the quarter')[:2] == ('earnings', 'Unclear')
    assert classify('ABC Industries bags order; SEBI penalty on ABC')[:2] == ('regulation_legal', 'Mixed')
    assert classify('ABC Industries announces record date for dividend')[:2] == ('corporate_action', 'Neutral')
    assert classify('ABC Industries in the news today')[:2] == ('other', 'Unclear')

def test_eligible_session_follows_publication_and_fails_closed_without_a_calendar():
    assert eligible_session('2026-09-07T06:40:00+05:30', hours) == ('2026-09-07', False)   # Monday, before the open
    assert eligible_session('2026-09-07T12:00:00+05:30', hours) == ('2026-09-08', True)    # released while trading
    assert eligible_session('2026-09-04T17:00:00+05:30', hours) == ('2026-09-07', False)   # Friday after the close
    assert eligible_session('2026-09-05T10:00:00+05:30', hours) == ('2026-09-07', False)   # weekend
    HOLIDAYS.add('2026-09-08')
    try: assert eligible_session('2026-09-07T16:00:00+05:30', hours) == ('2026-09-09', False)
    finally: HOLIDAYS.clear()
    def broken(_): raise MarketError('No verified calendar')
    assert eligible_session('2026-09-07T06:40:00+05:30', broken) == (None, None)

def test_a_corrected_article_adds_a_new_note_and_never_rewrites_the_first(session):
    stock(session)
    article(session, 'ABC Industries wins a contract', '2026-09-07T06:40:00+05:30', url='https://publisher.example/a')
    assert assess_new_articles(session, hours, observed_at='2026-09-07T06:45:00+05:30') == 1
    article(session, 'ABC Industries cancels a contract', '2026-09-07T06:40:00+05:30', received='2026-09-07T10:00:00+05:30', url='https://publisher.example/a')
    assert assess_new_articles(session, hours, observed_at='2026-09-07T10:05:00+05:30') == 1
    rows = session.scalars(select(EventAssessment).order_by(EventAssessment.id)).all()
    assert [r.effect for r in rows] == ['Positive', 'Negative']
    assert rows[0].assessed_at == '2026-09-07T01:15:00+00:00' and rows[0].eligible_session == '2026-09-07'
    # The market could react from publication; our late receipt changes the cutoff, not the reaction window.
    assert rows[1].eligible_session == '2026-09-07' and rows[1].published_during_session is False
    assert assess_new_articles(session, hours, observed_at='2026-09-07T10:06:00+05:30') == 0
    session.commit()
    with pytest.raises(IntegrityError, match='cannot be changed'):
        session.execute(update(EventAssessment).where(EventAssessment.id == rows[0].id).values(effect='Neutral'))
    session.rollback()
    assert session.get(EventAssessment, rows[0].id).effect == 'Positive'
    article(session, 'ABC Industries secures order', '2026-09-07T06:00:00+05:30', received='2026-09-07T12:00:00+05:30', url='https://publisher.example/b')
    with pytest.raises(ValueError, match='before it was received'):
        assess_new_articles(session, hours, observed_at='2026-09-07T11:00:00+05:30')

def test_an_ambiguous_company_mention_gets_no_note(session):
    stock(session, 'IDEA', 'Vodafone Idea Limited')
    matched = company_matches('An investment idea for this week', session.scalars(select(Instrument)).all())
    row = article(session, 'An investment idea for this week', '2026-09-07T06:40:00+05:30', symbols=matched)
    assert row.symbols == '[]' and assess_new_articles(session, hours) == 0

def test_reactions_keep_gap_and_session_separate_and_are_written_once(session):
    stock(session)
    bar(session, 'ABC', '2026-09-04', 100, 100)
    article(session, 'ABC Industries wins a contract', '2026-09-04T17:00:00+05:30')
    assess_new_articles(session, hours, observed_at='2026-09-04T17:05:00+05:30')
    assessment = session.scalar(select(EventAssessment))
    assert assessment.eligible_session == '2026-09-07'
    assert record_outcomes(session, hours, observed_at='2026-09-04T18:00:00+05:30') == 0
    bar(session, 'ABC', '2026-09-07', 102, 101)
    assert record_outcomes(session, hours, observed_at='2026-09-07T18:40:00+05:30') == 1
    outcome = session.get(EventOutcome, (assessment.id, 'session'))
    assert outcome.gap_pct == 2.0 and outcome.session_pct == pytest.approx(-0.98, abs=0.01) and outcome.change_pct == 1.0
    assert outcome.bars_available_at == '2026-09-07T13:05:00+00:00'
    assert record_outcomes(session, hours, observed_at='2026-09-07T18:41:00+05:30') == 0
    for day, close in [('2026-09-08', 103), ('2026-09-09', 104), ('2026-09-10', 105)]: bar(session, 'ABC', day, close, close)
    assert record_outcomes(session, hours, observed_at='2026-09-10T18:40:00+05:30') == 0
    bar(session, 'ABC', '2026-09-11', 106, 110)
    assert record_outcomes(session, hours, observed_at='2026-09-11T18:40:00+05:30') == 1
    five = session.get(EventOutcome, (assessment.id, 'five_sessions'))
    assert five.end_date == '2026-09-11' and five.change_pct == 10.0 and five.session_pct is None
    session.commit()
    with pytest.raises(IntegrityError, match='cannot be changed'):
        session.execute(update(EventOutcome).where(EventOutcome.assessment_id == assessment.id).values(session_pct=5))
    session.rollback()
    # The five-session bars are dated after this test's own "today"; a note reads only what its cutoff allows.
    assert 'five_sessions' not in (event_notes(session, 'ABC', cutoff='2026-09-08T00:00:00+05:30')[0]['outcome'] or {})
    note = event_notes(session, 'ABC', cutoff='2026-09-12T00:00:00+05:30')[0]
    assert note['review'].startswith('Positive read, but the stock fell 1.0% from open to close and gapped up 2.0%')
    assert note['outcome']['session']['gap_pct'] == 2.0 and note['outcome']['five_sessions']['change_pct'] == 10.0
    assert note['before']['status'] == 'Not enough history' and note['influences_predictions'] is False
    assert any('expectation' in x for x in note['unknowns'])
    assert event_notes(session, 'ABC', cutoff='2026-09-07T06:00:00+05:30')[0]['outcome'] is None
    # A note written after its own reaction is known must not count that reaction as "what happened before".
    from app.events import record_owner_assessment
    late = record_owner_assessment(session, assessment.article_id, 'ABC', 'order_contract', 'Positive',
        'Owner note written a week later, after the reaction was public.', hours=hours, observed_at='2026-09-14T10:00:00+05:30')
    late_note = next(n for n in event_notes(session, 'ABC', cutoff='2026-09-14T11:00:00+05:30') if n['id'] == late.id)
    assert late_note['before']['count'] == 0 and late_note['assessor'] == 'owner'

def test_comparisons_use_only_reactions_known_at_the_cutoff_and_count_syndicated_copies_once(session):
    stock(session); stock(session, 'XYZ', 'XYZ Motors Limited'); stock(session, 'PQR', 'PQR Steel Limited', sector='Other')
    moves = [(f'2026-0{m}-1{d}', pct) for (m, d), pct in zip([(3, 0), (4, 1), (5, 2), (6, 3)], [1.0, -0.5, 2.0, 0.1])]
    for day, pct in moves: past_event(session, 'ABC', day, pct, 0.4, f'{day}T18:40:00+05:30', copies=3 if day.startswith('2026-04') else 1)
    past_event(session, 'PQR', '2026-07-14', -1.0, -0.2, '2026-07-14T18:40:00+05:30')   # other sector, known first
    past_event(session, 'XYZ', '2026-08-11', 0.5, 0.0, '2026-08-11T18:40:00+05:30')     # same sector, known later
    everything = comparable_events(session, 'ABC', 'order_contract', 'Positive', cutoff='2026-09-01T00:00:00+05:30')
    assert everything['scope'] == 'Test companies' and everything['count'] == 5 and everything['articles'] == 7
    assert everything['status'] == 'ok' and everything['share_positive_after_costs'] == 60 and everything['median_session_pct'] == 0.5
    nothing_known = comparable_events(session, 'ABC', 'order_contract', 'Positive', cutoff='2026-07-14T18:00:00+05:30')
    assert nothing_known['scope'] == 'all tracked companies' and nothing_known['count'] == 4 and nothing_known['status'] == 'Not enough history'
    only_pqr = comparable_events(session, 'ABC', 'order_contract', 'Positive', cutoff='2026-07-15T00:00:00+05:30')
    assert only_pqr['scope'] == 'all tracked companies' and only_pqr['count'] == 5 and only_pqr['status'] == 'ok'
    assert comparable_events(session, 'ABC', 'earnings', 'Unclear', cutoff='2026-09-01T00:00:00+05:30')['count'] == 0
    own = history_summary(session, 'ABC')
    assert own[0]['event_type'] == 'order_contract' and own[0]['count'] == 4 and own[0]['articles'] == 6

def test_notes_have_no_path_into_the_daily_rule():
    source = inspect.getsource(engine_module)
    assert 'EventAssessment' not in source and 'EventOutcome' not in source and 'events' not in source

def test_scheduler_assesses_after_collection_and_records_reactions_at_close(session, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, 'collect_news', lambda s: [{'source': 'Fixture', 'status': 'ok', 'added': 0}])
    monkeypatch.setattr(scheduler, 'assess_new_articles', lambda s, hours=None: calls.append(('assess', callable(hours))) or 3)
    monkeypatch.setattr(scheduler, 'record_outcomes', lambda s, hours=None: calls.append(('outcomes', callable(hours))) or 2)
    monkeypatch.setattr(scheduler, 'ingest_daily', lambda s, p, d: {'accepted': 0})
    monkeypatch.setattr(scheduler, 'resolve_day', lambda s, d: 0)
    monkeypatch.setattr(scheduler, 'previous_session', lambda s, p, d: '2026-09-04')
    provider = SimpleNamespace(id='yfinance')
    assert scheduler.news_job(session, provider)['assessed'] == 3
    assert scheduler.close_day(session, provider, '2026-09-07')['event_outcomes'] == 2
    assert scheduler.load_history(session, provider, '2026-09-07')['event_outcomes'] == 2
    assert calls == [('assess', True), ('outcomes', True), ('outcomes', True)]

@pytest.fixture
def client(session):
    seed_demo(session)
    from app.main import app
    app.dependency_overrides[session_dependency] = lambda: session
    client = TestClient(app)
    yield client
    client.close(); app.dependency_overrides.clear()

def test_owner_notes_are_versioned_validated_and_shown_beside_the_news(client, session):
    row = article(session, 'Reliance Industries wins a contract', '2026-09-07T06:40:00+05:30', symbols=('RELIANCE',))
    session.commit()
    path = f'/api/events/{row.id}/assessment'
    assert client.post(path, json={'symbol': 'RELIANCE', 'event_type': 'order_contract', 'effect': 'Great', 'facts': 'A big win for them'}).status_code == 422
    assert client.post(path, json={'symbol': 'RELIANCE', 'event_type': 'order_contract', 'effect': 'Positive', 'facts': 'short'}).status_code == 422
    first = client.post(path, json={'symbol': 'RELIANCE', 'event_type': 'order_contract', 'effect': 'Positive',
        'facts': 'Contract worth about 2% of annual revenue; not previously announced.', 'expectation': 'None published'})
    assert first.status_code == 201, first.text
    note = first.json()['note']
    assert note['assessor'] == 'owner' and note['eligible_session'] == '2026-09-07' and note['influences_predictions'] is False
    second = client.post(path, json={'symbol': 'RELIANCE', 'event_type': 'order_contract', 'effect': 'Neutral',
        'facts': 'On reflection the contract is small relative to the order book.'})
    assert second.status_code == 201
    stock_page = client.get('/api/stocks/RELIANCE').json()
    assert [n['effect'] for n in stock_page['events']] == ['Neutral', 'Positive']
    assert stock_page['event_options']['effects'][0] == 'Positive' and stock_page['patterns'] == []
    assert client.post('/api/events/999999/assessment', json={'symbol': 'RELIANCE', 'event_type': 'other', 'effect': 'Unclear', 'facts': 'Nothing to add here'}).status_code == 404
    listed = client.get('/api/news').json()['articles'][0]
    assert listed['impact'] == 'Neutral / Positive · owner read' and len(listed['assessments']) == 2
    assert client.get('/api/health').json()['checks'][4]['name'] == 'Event notes'
