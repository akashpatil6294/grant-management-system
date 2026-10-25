from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from psycopg.rows import dict_row

from app import database


@pytest.mark.parametrize('value', [
    'postgresql://user:example@db.example.com:5432/postgres?sslmode=require',
    'DATABASE_URL=postgresql://user:example@db.example.com:5432/postgres?sslmode=require',
    'DATABASE_URL=postgresql+psycopg://user:example@db.example.com:5432/postgres?sslmode=require',
    'postgresql+psycopg2://user:example@db.example.com:5432/postgres?sslmode=require',
    ' "postgresql://user:example@db.example.com:5432/postgres?sslmode=require" ',
])
def test_connection_string_accepts_copied_configuration(value):
    assert database.connection_string(value) == 'postgresql://user:example@db.example.com:5432/postgres?sslmode=require'


def test_connection_string_preserves_encoded_password():
    value = 'postgresql://user:example%40%23%3A%2F@db.example.com/postgres'
    assert database.connection_string(value) == value


@pytest.mark.parametrize('value', ['', 'psql postgresql://user:DO_NOT_EXPOSE@db.example.com/postgres', 'not-a-connection-DO_NOT_EXPOSE'])
def test_invalid_connection_string_returns_safe_actionable_error(value):
    with pytest.raises(HTTPException) as error:
        database.connection_string(value)
    assert error.value.status_code == 503
    assert 'DATABASE_URL is invalid' in error.value.detail
    assert 'DO_NOT_EXPOSE' not in error.value.detail


@pytest.mark.parametrize('fail', [False, True])
def test_pooler_compatible_connection_is_closed_on_success_and_failure(monkeypatch, fail):
    monkeypatch.setattr(database, 'settings', lambda: SimpleNamespace(database_url='postgresql://test.invalid/test'))
    connect = MagicMock()
    monkeypatch.setattr(database.psycopg, 'connect', connect)
    context = connect.return_value
    conn = context.__enter__.return_value

    def transaction():
        with database.connection() as actual:
            assert actual is conn
            if fail:
                raise ValueError('Transaction failed')

    if fail:
        with pytest.raises(ValueError, match='Transaction failed'):
            transaction()
    else:
        transaction()

    connect.assert_called_once_with(
        'postgresql://test.invalid/test',
        row_factory=dict_row,
        connect_timeout=10,
        prepare_threshold=None,
    )
    conn.execute.assert_called_once_with('SET LOCAL search_path TO private, public')
    context.__exit__.assert_called_once()
    assert context.__exit__.call_args.args[0] is (ValueError if fail else None)
