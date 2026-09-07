import pytest
from sqlalchemy.orm import Session
from app.db import build_engine,initialize

@pytest.fixture
def session(tmp_path):
    engine=build_engine(f'sqlite:///{tmp_path}/test.db');initialize(engine)
    with Session(engine,expire_on_commit=False) as session:yield session
    engine.dispose()
