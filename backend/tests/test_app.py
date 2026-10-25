from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.auth import current_staff
from app import auth
from app.schemas import Grant, Expense, Donor, ImpactUpdate
from app.services import deadline_status, summarize

client = TestClient(app)
ID = '00000000-0000-0000-0000-000000000001'


@pytest.fixture(autouse=True)
def reset_overrides():
    yield
    app.dependency_overrides.clear()


def test_health_without_credentials():
    assert client.get('/health').json() == {'status': 'ok'}


@pytest.mark.parametrize('path', ['/api/me','/api/donors','/api/grants','/api/dashboard', f'/api/grants/{ID}/expenses', f'/api/grants/{ID}/budget-categories', f'/api/grants/{ID}/reporting-deadlines',f'/api/grants/{ID}/impact-metrics',f'/api/impact-metrics/{ID}/updates'])
def test_business_endpoints_require_auth(path):
    assert client.get(path).status_code == 401


def test_write_requires_auth():
    assert client.post('/api/donors',json={'name':'Example'}).status_code == 401


def test_invalid_expense_rejected_before_database():
    app.dependency_overrides[current_staff] = lambda: {'user_id': ID}
    response = client.post(f'/api/grants/{ID}/expenses',json={'budget_category_id':ID,'amount':'0.001','expense_date':'2026-01-01','description':'Too precise'})
    assert response.status_code == 422


@pytest.mark.parametrize('amount', ['0','-1','0.001','NaN','Infinity','1000000000000.00'])
def test_bad_amounts(amount):
    with pytest.raises(ValidationError):
        Expense(budget_category_id=ID,amount=amount,expense_date='2026-01-01',description='Test')


def test_decimal_amount_is_exact():
    e = Expense(budget_category_id=ID,amount='0.10',expense_date='2026-01-01',description='Test')
    assert e.amount + Decimal('0.20') == Decimal('0.30')


def test_grant_dates():
    with pytest.raises(ValidationError):
        Grant(donor_id=ID,name='Test',award_amount='100',currency='USD',start_date='2026-02-01',end_date='2026-01-01')


def test_impact_dates():
    with pytest.raises(ValidationError):
        ImpactUpdate(period_start='2026-02-01',period_end='2026-01-01',actual_value='1')


@pytest.mark.parametrize('body',[{'name':'   '},{'name':'Test','contact_email':'not-an-email'},{'name':'Test','user_id':ID}])
def test_invalid_donor(body):
    with pytest.raises(ValidationError):
        Donor(**body)


def test_deadline_boundaries():
    today = date(2026,10,25)
    assert deadline_status(today - timedelta(days=1),None,today) == 'overdue'
    assert deadline_status(today,None,today) == 'due_soon'
    assert deadline_status(today + timedelta(days=14),None,today) == 'due_soon'
    assert deadline_status(today + timedelta(days=15),None,today) == 'upcoming'
    assert deadline_status(today - timedelta(days=1),'submitted',today) == 'submitted'


def test_totals_keep_currencies_separate():
    rows = [dict(currency=c,award_amount=Decimal('1.00'),allocated=Decimal('0.30'),spent=Decimal('0.10')) for c in ['USD','USD','INR']]
    totals = {r['currency']:r for r in summarize(rows)}
    assert totals['USD']['spent'] == Decimal('0.20')
    assert totals['USD']['remaining'] == Decimal('1.80')
    assert totals['INR']['awarded'] == Decimal('1.00')


def setup_auth(monkeypatch, response):
    from types import SimpleNamespace
    monkeypatch.setattr(auth,'settings',lambda:SimpleNamespace(supabase_url='https://example.supabase.co',supabase_publishable_key='test-key'))
    monkeypatch.setattr(auth.httpx,'get',lambda *args,**kwargs:response)


def test_invalid_token(monkeypatch):
    setup_auth(monkeypatch,httpx.Response(401))
    assert client.get('/api/me',headers={'Authorization':'Bearer invalid'}).status_code == 401


def test_auth_provider_failure(monkeypatch):
    setup_auth(monkeypatch,httpx.Response(500))
    assert client.get('/api/me',headers={'Authorization':'Bearer test'}).status_code == 503


@pytest.mark.parametrize('member,expected',[(None,403),({'user_id':UUID(ID),'display_name':'Test staff','is_active':True},200)])
def test_staff_membership(monkeypatch, member, expected):
    setup_auth(monkeypatch,httpx.Response(200,json={'id':ID}))
    class FakeConnection:
        def execute(self,*args):
            return self
        def fetchone(self):
            return member
    @contextmanager
    def fake_connection():
        yield FakeConnection()
    monkeypatch.setattr(auth,'connection',fake_connection)
    assert client.get('/api/me',headers={'Authorization':'Bearer test'}).status_code == expected


def test_decimal_json_serialization():
    from app.main import result
    assert result({'amount':Decimal('0.10')}).body == b'{"amount":"0.10"}'
