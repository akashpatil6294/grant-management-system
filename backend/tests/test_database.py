from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from psycopg.rows import dict_row

from app import database


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
