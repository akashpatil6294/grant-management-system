from contextlib import contextmanager

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.mark.parametrize('error,expected', [
    (psycopg.errors.UndefinedTable, 'Database tables are missing'),
    (psycopg.errors.InvalidSchemaName, 'Database tables are missing'),
    (psycopg.errors.InsufficientPrivilege, 'lacks application permissions'),
    (psycopg.OperationalError, 'Database is unavailable'),
])
def test_readiness_reports_safe_database_diagnostics(monkeypatch, caplog, error, expected):
    @contextmanager
    def fail():
        raise error('SENSITIVE_CONNECTION_DETAILS')
        yield
    monkeypatch.setattr(main, 'connection', fail)
    with TestClient(main.app) as client:
        response = client.get('/ready')
    assert response.status_code == 503
    assert expected in response.json()['detail']
    assert 'SENSITIVE_CONNECTION_DETAILS' not in response.text
    assert 'SENSITIVE_CONNECTION_DETAILS' not in caplog.text
    assert f'type={error.__name__}' in caplog.text
    assert 'sqlstate=' in caplog.text
