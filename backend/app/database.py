from contextlib import contextmanager
from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row
from .config import settings


@contextmanager
def connection():
    if not settings().database_url:
        raise HTTPException(503, 'Database is not configured.')
    with psycopg.connect(settings().database_url, row_factory=dict_row, connect_timeout=10) as conn:
        conn.execute('SET LOCAL search_path TO private, public')
        yield conn
