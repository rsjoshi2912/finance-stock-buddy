from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Instrument(Base):
    __tablename__ = 'instruments'
    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    sector: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), default='stock')
    member_from: Mapped[str] = mapped_column(String(10), default='2000-01-01')
    member_to: Mapped[str | None] = mapped_column(String(10), nullable=True)

class Price(Base):
    __tablename__ = 'prices'
    __table_args__ = (UniqueConstraint('symbol','date'), CheckConstraint('open > 0 AND close > 0 AND high >= low'))
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey('instruments.symbol'))
    date: Mapped[str] = mapped_column(String(10), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(Text)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

class RawRecord(Base):
    __tablename__ = 'raw_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text)
    received_at: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

class Evidence(Base):
    __tablename__ = 'evidence'
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, unique=True)
    body: Mapped[str] = mapped_column(String(2000))
    published_at: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[str] = mapped_column(String(32))
    sentiment: Mapped[float] = mapped_column(Float, default=0)

class Prediction(Base):
    __tablename__ = 'predictions'
    __table_args__ = (UniqueConstraint('date','symbol','model_version','horizon'), CheckConstraint('prob_up >= 0 AND prob_up <= 1'), CheckConstraint("direction IN ('UP','DOWN')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey('instruments.symbol'))
    date: Mapped[str] = mapped_column(String(10), index=True)
    data_cutoff: Mapped[str] = mapped_column(String(32))
    horizon: Mapped[str] = mapped_column(String(30), default='open_close')
    direction: Mapped[str] = mapped_column(String(8))
    prob_up: Mapped[float] = mapped_column(Float)
    expected_low: Mapped[float] = mapped_column(Float)
    expected_high: Mapped[float] = mapped_column(Float)
    invalidation: Mapped[float] = mapped_column(Float)
    ref_price: Mapped[float] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(80))
    sources: Mapped[str] = mapped_column(Text)
    allocation: Mapped[float] = mapped_column(Float, default=1000)
    cost_rate: Mapped[float] = mapped_column(Float, default=0.0015)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

class Resolution(Base):
    __tablename__ = 'resolutions'
    prediction_id: Mapped[int] = mapped_column(ForeignKey('predictions.id'), primary_key=True)
    entry: Mapped[float] = mapped_column(Float)
    exit: Mapped[float] = mapped_column(Float)
    right: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    costs: Mapped[float] = mapped_column(Float)
    cause: Mapped[str | None] = mapped_column(String(50), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[str] = mapped_column(String(32))

class ModelVersion(Base):
    __tablename__ = 'model_versions'
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    brier: Mapped[float | None] = mapped_column(Float, nullable=True)

class Improvement(Base):
    __tablename__ = 'improvements'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    created_at: Mapped[str] = mapped_column(String(32))

class JobRun(Base):
    __tablename__ = 'job_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    rows: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text)
    started_at: Mapped[str] = mapped_column(String(32))

class TokenBudget(Base):
    __tablename__ = 'token_budgets'
    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    reserved: Mapped[int] = mapped_column(Integer, default=0)

class Setting(Base):
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)

class InstrumentMapping(Base):
    __tablename__ = 'instrument_mappings'
    symbol: Mapped[str] = mapped_column(ForeignKey('instruments.symbol'), primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(100), unique=True)
    provider: Mapped[str] = mapped_column(String(30), default='upstox')

class Quote(Base):
    """Latest display snapshot only. Never used to resolve or train a daily call."""
    __tablename__ = 'quotes'
    symbol: Mapped[str] = mapped_column(ForeignKey('instruments.symbol'), primary_key=True)
    price: Mapped[float] = mapped_column(Float)
    change: Mapped[float] = mapped_column(Float)
    market_at: Mapped[str] = mapped_column(String(32))
    received_at: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(30))

class ScheduledRun(Base):
    __tablename__ = 'scheduled_runs'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default='')
