import json
from html.parser import HTMLParser

import httpx
import pytest
from sqlalchemy import select

from app.analytics import dashboard
from app.briefs import evening, morning, plain_text, validate
from app.events import assess_new_articles, classify, comparable_events, event_notes, history_summary, record_outcomes
from app.models import EventAssessment, EventOutcome, Setting
from test_engine import build_ten_day_fixture
from test_events import article, bar, hours, past_event, stock


def test_later_recording_never_appears_in_a_past_news_view(session):
    stock(session)
    past_event(session, 'ABC', '2026-09-07', 1, 0, '2026-09-07T18:40:00+05:30')
    outcome = session.scalar(select(EventOutcome))
    session.expunge(outcome)
    # Build a separate late-recorded case, without editing an immutable database row.
    other = article(session, 'ABC later recorded case', '2026-09-08T06:00:00+05:30')
    note = EventAssessment(article_id=other.id, symbol='ABC', event_type='order_contract', effect='Positive',
        facts='Fixture note', assessor='rules_v1', evidence_hash=other.content_hash, eligible_session='2026-09-08',
        assessed_at='2026-09-08T01:00:00+00:00')
    session.add(note); session.flush()
    session.add(EventOutcome(assessment_id=note.id, horizon='session', start_date='2026-09-08', end_date='2026-09-08',
        reference_close=100, open=100, close=102, gap_pct=0, session_pct=2, change_pct=2,
        bars_available_at='2026-09-08T13:10:00+00:00', recorded_at='2026-09-10T13:10:00+00:00'))
    session.flush()
    cutoff = '2026-09-09T00:00:00+00:00'
    assert comparable_events(session, 'ABC', 'order_contract', 'Positive', cutoff=cutoff)['count'] == 1
    assert history_summary(session, 'ABC', cutoff=cutoff)[0]['count'] == 1
    assert next(n for n in event_notes(session, 'ABC', cutoff=cutoff) if n['id'] == note.id)['outcome'] is None


def test_missing_bar_cannot_be_replaced_with_a_later_session(session):
    stock(session)
    article(session, 'ABC wins order', '2026-09-04T17:00:00+05:30')
    assess_new_articles(session, hours, observed_at='2026-09-04T18:00:00+05:30')
    for day in ['2026-09-03', '2026-09-07', '2026-09-08', '2026-09-10', '2026-09-11', '2026-09-14']:
        bar(session, 'ABC', day, 100, 101)
    assert record_outcomes(session, hours, observed_at='2026-09-15T00:00:00+00:00') == 0  # missing prior session
    bar(session, 'ABC', '2026-09-04', 100, 100)
    assert record_outcomes(session, hours, observed_at='2026-09-15T00:00:00+00:00') == 1
    assert session.scalar(select(EventOutcome).where(EventOutcome.horizon == 'five_sessions')) is None
    bar(session, 'ABC', '2026-09-09', 100, 101)
    assert record_outcomes(session, hours, observed_at='2026-09-15T00:00:00+00:00') == 1
    assert session.scalar(select(EventOutcome).where(EventOutcome.horizon == 'five_sessions')).end_date == '2026-09-11'


def test_negation_and_multiple_companies_do_not_get_an_actionable_effect(session):
    assert classify('ABC denies a SEBI probe')[1] == 'Unclear'
    assert classify('ABC may win a contract')[1] == 'Unclear'
    stock(session); stock(session, 'XYZ', 'XYZ Limited')
    article(session, 'ABC wins order while XYZ faces penalty', '2026-09-07T06:00:00+05:30', symbols=('ABC', 'XYZ'))
    assert assess_new_articles(session, hours, observed_at='2026-09-07T06:30:00+05:30') == 2
    assert all(n.effect == 'Unclear' and n.assessor == 'rules_v2' for n in session.scalars(select(EventAssessment)))
    assert assess_new_articles(session, hours, observed_at='2026-09-07T06:31:00+05:30') == 0


def test_telegram_escapes_imported_content_and_keeps_all_ten_calls(session):
    build_ten_day_fixture(session)
    data = dashboard(session)
    data['calls'][0]['symbol'] = 'M&M'
    data['calls'][0]['reason'] = '<script>alert(1)</script> & unexpected <b>news</b>'
    data['calls'][0]['explanation'] = '<a href="evil">wrong</a>'
    for render in (morning, evening):
        message = render(data)
        assert len(plain_text(message).encode('utf-16-le')) // 2 <= 4000
        assert 'M&amp;M' in message and '<script>' not in message and '<a ' not in message
        assert all(c['symbol'] in plain_text(message) for c in data['calls'])
        class Tags(HTMLParser):
            def handle_starttag(self, tag, attrs):
                assert tag == 'b' and not attrs
        Tags().feed(message)
    assert 'uncalibrated rule scores' in morning(data) and 'indices scored for direction only' in morning(data)
    assert 'KEEP IN MIND' not in morning(data)
    with pytest.raises(ValueError): validate('🟢' * 2001)


def test_sender_uses_html_and_keeps_duplicate_protection(session, monkeypatch):
    from app import jobs
    monkeypatch.setattr(jobs, 'MODE', 'live')
    for key, value in {'TELEGRAM_ENABLED':'true','TELEGRAM_BOT_TOKEN':'fixture','TELEGRAM_CHAT_ID':'123'}.items():
        monkeypatch.setenv(key, value)
    session.add(Setting(key='telegram_verified_chat_id', value='123')); session.commit()
    sent = []
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'ok':True})
    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(jobs.httpx, 'Client', lambda **kwargs: client)
    jobs.send_telegram('<b>Test &amp; preview</b>', 'evening', '2026-09-08', session)
    assert sent == [{'chat_id':'123','text':'<b>Test &amp; preview</b>','parse_mode':'HTML','link_preview_options':{'is_disabled':True}}]
    with pytest.raises(ValueError, match='already attempted'):
        jobs.send_telegram('Test', 'evening', '2026-09-08', session)
