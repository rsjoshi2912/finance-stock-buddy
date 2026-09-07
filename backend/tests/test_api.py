import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import session_dependency
from app.demo import seed_demo
from app.models import Improvement

@pytest.fixture
def client(session):
    seed_demo(session)
    app.dependency_overrides[session_dependency]=lambda:session
    client=TestClient(app)
    yield client
    client.close();app.dependency_overrides.clear()

def test_pages_read_real_api_data(client):
    data=client.get('/api/today').json()
    assert data['mode']=='demo' and len(data['calls'])==10
    for endpoint in ['track-record','health','stocks','stocks/RELIANCE','brief/morning','brief/evening','quotes','news']:
        response=client.get('/api/'+endpoint)
        assert response.status_code==200,(endpoint,response.text)
    assert client.get('/api/stocks/UNKNOWN').status_code==404
    assert client.get('/api/export.csv').text.startswith('date,symbol,direction')
    assert client.get('/api/news').json()['influences_predictions'] is False

def test_backlog_never_changes_model(client,session):
    idea=session.scalar(select(Improvement))
    before=client.get('/api/health').json()['models']
    assert client.post(f'/api/improvements/{idea.id}',json={'decision':'queued'}).status_code==200
    assert client.post(f'/api/improvements/{idea.id}',json={'decision':'skipped'}).status_code==409
    assert client.get('/api/health').json()['models']==before

def test_owner_auth_and_cross_site_writes(client,monkeypatch):
    monkeypatch.setenv('OWNER_PASSWORD','test-only-password')
    assert client.get('/api/today').status_code==401
    assert client.get('/api/today',auth=('ravi','test-only-password')).status_code==200
    assert client.post('/api/improvements/1',json={'decision':'queued'},headers={'Origin':'https://untrusted.example'},auth=('ravi','test-only-password')).status_code==403

def test_pages_origin_preflight_and_private_api(client,monkeypatch):
    from app.main import FRONTEND_ORIGINS
    origin='https://rsjoshi2912.github.io'
    FRONTEND_ORIGINS.append(origin)
    monkeypatch.setenv('OWNER_PASSWORD','test-only-password')
    try:
        response=client.options('/api/session',headers={'Origin':origin,
            'Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'authorization'})
        assert response.status_code==200
        assert response.headers['access-control-allow-origin']==origin
        assert client.get('/api/session',headers={'Origin':origin}).status_code==401
        signed=client.get('/api/session',headers={'Origin':origin},auth=('ravi','test-only-password'))
        assert signed.status_code==200 and signed.json()['signed_in']
        assert signed.headers['cache-control']=='no-store'
        assert signed.headers['access-control-allow-origin']==origin
        denied=client.options('/api/session',headers={'Origin':'https://unknown.example',
            'Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'authorization'})
        assert denied.status_code==400
    finally:
        FRONTEND_ORIGINS.remove(origin)
