from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.analytics import dashboard, records, serialize, track_record
from app.briefs import evening
from app.engine import cutoff_for, resolve_day, utcstamp
from app.learning import features_for, training_rows
from app.models import Instrument, Prediction, Price, Resolution
from test_engine import build_ten_day_fixture


def test_flat_calls_still_pay_costs_in_every_money_breakdown(session):
    session.add(Instrument(symbol='FLAT', name='Flat stock', sector='Test'))
    session.flush()
    prediction = Prediction(
        symbol='FLAT', date='2026-09-01', data_cutoff=cutoff_for('2026-09-01'),
        direction='UP', prob_up=.6, expected_low=98, expected_high=102,
        invalidation=98, ref_price=100, rank=1, rationale='Fixture',
        model_version='momentum_research_v1', sources='[]', synthetic=True,
    )
    session.add(prediction)
    session.flush()
    session.add(Resolution(
        prediction_id=prediction.id, entry=100, exit=100, right=None,
        pnl=-1.5, baseline_pnl=-1.5, costs=1.5,
        resolved_at=utcstamp('2026-09-01T18:30:00+05:30'),
    ))
    session.flush()
    report = track_record(session)
    assert report['summary']['pnl'] == -1.5
    assert report['summary']['total'] == 0
    assert report['months'][0]['pnl'] == -1.5
    assert all(group['pnl'] == -1.5 for group in report['groups'])


def test_evening_note_lists_unresolved_names(session):
    build_ten_day_fixture(session)
    data = dashboard(session)
    pending = data['calls'][0]
    pending.update(result='Pending', pnl=None, baseline_pnl=None)
    note = evening(data)
    assert f'1 still pending ({pending["symbol"]})' in note
    assert 'Totals may change' in note
    assert len(note) <= 4000


def test_late_outcomes_do_not_rewrite_a_past_accuracy_claim(session):
    build_ten_day_fixture(session)
    history = records(session)
    current = history[-1]
    original = serialize(*current, history)
    late = next(row for row in history if row[0].symbol == current[0].symbol and row[0].date < current[0].date)
    # Emulate a result that arrived only after this prediction was written.
    # This is an in-memory read fixture, never an UPDATE to an immutable row.
    session.expunge(late[1])
    late[1].resolved_at = '2099-01-01T00:00:00+00:00'
    assert serialize(*current, history)['past_total'] == original['past_total'] - 1


def test_training_features_ignore_late_prices_and_labels(session):
    days = build_ten_day_fixture(session)
    cutoff = cutoff_for(days[-1])
    before = features_for(session, 'TEST0', cutoff)
    assert before is not None and len(before) == 6
    # A missing older bar received years later must never enter the features.
    session.add(Price(
        symbol='TEST0', date='2026-07-18', open=10000, high=10000,
        low=10000, close=10000, volume=100000,
        published_at=utcstamp('2026-07-18T18:00:00+05:30'),
        ingested_at='2099-01-01T00:00:00+00:00', source='fixture', synthetic=True,
    ))
    session.flush()
    assert features_for(session, 'TEST0', cutoff) == before
    rows = training_rows(session, cutoff, allow_sample=True)
    assert rows and all(row['date'] < days[-1] for row in rows)
    assert all(row['label_available_at'] <= cutoff for row in rows)
    assert training_rows(session, cutoff, allow_sample=False) == []


def test_live_resolution_records_actual_processing_time(session):
    session.add(Instrument(symbol='LIVE', name='Live fixture', sector='Test'))
    session.flush()
    session.add(Prediction(
        symbol='LIVE', date='2026-01-01', data_cutoff=cutoff_for('2026-01-01'),
        direction='UP', prob_up=.6, expected_low=98, expected_high=102,
        invalidation=98, ref_price=100, rank=1, rationale='Fixture',
        model_version='momentum_research_v1', sources='[]', synthetic=False,
    ))
    session.add(Price(
        symbol='LIVE', date='2026-01-01', open=100, high=101, low=99,
        close=101, volume=100, published_at='2026-01-01T13:00:00+00:00',
        ingested_at='2026-01-02T13:00:00+00:00', source='fixture', synthetic=False,
    ))
    session.flush()
    before = datetime.now(timezone.utc).replace(microsecond=0)
    assert resolve_day(session, '2026-01-01') == 1
    resolved = session.scalar(select(Resolution))
    assert datetime.fromisoformat(resolved.resolved_at) >= before
