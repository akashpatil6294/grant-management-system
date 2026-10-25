from contextlib import contextmanager
from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict
from .config import settings


def connection_string(value: str) -> str:
    """Accept common copied env/SQLAlchemy forms without logging credentials."""
    value = value.strip()
    # Hosting dashboards expect a value, but users may paste a complete .env line.
    while value.upper().startswith('DATABASE_URL='):
        value = value.split('=', 1)[1].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    for scheme in ('postgresql+psycopg://', 'postgresql+psycopg2://'):
        if value.startswith(scheme):
            value = 'postgresql://' + value[len(scheme):]
            break
    try:
        if not value:
            raise ValueError('Empty connection string')
        conninfo_to_dict(value)
    except (psycopg.ProgrammingError, ValueError):
        raise HTTPException(
            503,
            'DATABASE_URL is invalid. In Render, set its value to the PostgreSQL '
            'connection URI from Supabase Connect (postgresql://...). '
            'Do not paste a shell command. URL-encode special characters in the password.',
        ) from None
    return value


@contextmanager
def connection():
    if not settings().database_url:
        raise HTTPException(503, 'Database is not configured.')
    # Supabase's transaction pooler must not reuse connection-local prepared statements.
    # Each transaction opens and closes its own connection; no application pool is used.
    with psycopg.connect(
        connection_string(settings().database_url),
        row_factory=dict_row,
        connect_timeout=10,
        prepare_threshold=None,
    ) as conn:
        conn.execute('SET LOCAL search_path TO private, public')
        yield conn
