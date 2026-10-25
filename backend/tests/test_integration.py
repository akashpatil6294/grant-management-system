"""Run via database/npm run test:api against an isolated, empty PGlite instance.

Authentication is overridden only inside tests. No bypass exists in the application.
"""
import os
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import current_staff
from app.config import settings

pytestmark = pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Run database/npm run test:api for isolated PostgreSQL API tests')
STAFF = UUID('00000000-0000-0000-0000-000000000001')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', os.environ['TEST_DATABASE_URL'])
    settings.cache_clear()
    app.dependency_overrides[current_staff] = lambda: {'user_id': STAFF, 'display_name': 'Test staff'}
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    settings.cache_clear()


def test_core_api_workflow(client):
    def post(path, body):
        response = client.post('/api' + path, json=body)
        assert response.status_code == 201, response.text
        return response.json()
    assert client.get('/ready').status_code == 200
    donor = post('/donors', {'name': 'Fictional API donor', 'contact_email': 'donor@example.org'})
    assert client.patch('/api/donors/' + donor['id'],json={'name':'Edited donor','is_active':True}).status_code == 200
    grant_body = dict(donor_id=donor['id'],name='API grant',award_amount='100.00',currency='USD',start_date='2026-01-01',end_date='2026-12-31',status='active')
    grant = post('/grants',grant_body)
    root = '/grants/' + grant['id']
    assert client.get('/api'+root).json()['donor_name'] == 'Edited donor'
    assert len(client.get('/api/grants?donor_id='+donor['id']).json()) == 1
    assert client.patch('/api'+root,json={**grant_body,'name':'Edited grant'}).status_code == 200
    category = post(root+'/budget-categories',dict(name='Supplies',allocated_amount='80.00'))
    assert client.post('/api'+root+'/budget-categories',json=dict(name='Excess',allocated_amount='20.01')).status_code == 409
    expense_body = dict(budget_category_id=category['id'],amount='0.10',expense_date='2026-01-02',description='Test purchase')
    expense = post(root+'/expenses',expense_body)
    post(root+'/expenses',{**expense_body,'amount':'0.20'})
    assert client.post('/api'+root+'/expenses',json={**expense_body,'amount':'79.71'}).status_code == 409
    assert client.patch('/api/budget-categories/'+category['id'],json=dict(name='Supplies',allocated_amount='0.29')).status_code == 409
    assert client.patch('/api'+root,json={**grant_body,'award_amount':'79.99'}).status_code == 409
    assert client.patch('/api/expenses/'+expense['id'],json={**expense_body,'description':'Corrected description'}).status_code == 200
    deadline = post(root+'/reporting-deadlines',dict(title='Progress report',due_date='2026-01-01'))
    assert client.patch('/api/reporting-deadlines/'+deadline['id'],json=dict(title='Progress report',due_date='2026-01-01',submitted=True)).status_code == 200
    assert client.get('/api'+root+'/reporting-deadlines').json()[0]['status'] == 'submitted'
    metric = post(root+'/impact-metrics',dict(name='Meals',unit='meals',target_value='100'))
    update = dict(period_start='2026-01-01',period_end='2026-01-07',actual_value='15')
    post('/impact-metrics/'+metric['id']+'/updates',update)
    assert client.post('/api/impact-metrics/'+metric['id']+'/updates',json=update).status_code == 409
    response = client.get('/api/dashboard?grant_id='+grant['id'])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['grant_count'] == 1
    assert data['totals'][0]['spent'] == '0.30'
    assert data['totals'][0]['remaining'] == '99.70'
    assert data['impact'][0]['actual_value'] == '15.00'
    assert len(client.get('/api'+root+'/expenses?limit=1&offset=1').json()) == 1
    assert client.get('/api/grants/00000000-0000-0000-0000-000000000099').status_code == 404
    assert client.patch('/api'+root,json={**grant_body,'status':'closed'}).status_code == 200
    assert client.post('/api'+root+'/expenses',json=expense_body).status_code == 409
