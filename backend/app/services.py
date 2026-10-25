from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
from fastapi import HTTPException
from psycopg import sql


def one(conn, table: str, record_id: UUID):
    row = conn.execute(sql.SQL('SELECT * FROM {} WHERE id=%s').format(sql.Identifier(table)), (record_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Record not found.')
    return row


def save(conn, table: str, data: dict, record_id: UUID | None = None):
    columns = list(data)
    if record_id:
        one(conn, table, record_id)
        query = sql.SQL('UPDATE {} SET {} WHERE id=%s RETURNING *').format(
            sql.Identifier(table), sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(c)) for c in columns))
        params = [*data.values(), record_id]
    else:
        query = sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns)),
            sql.SQL(',').join(sql.Placeholder() for _ in columns))
        params = list(data.values())
    return conn.execute(query, params).fetchone()


def lock_grant(conn, grant_id):
    if not conn.execute('SELECT id FROM grants WHERE id=%s FOR UPDATE', (grant_id,)).fetchone():
        raise HTTPException(404, 'Grant not found.')


def deadline_status(due: date, submitted_at, today: date):
    if submitted_at:
        return 'submitted'
    if due < today:
        return 'overdue'
    if due <= today + timedelta(days=14):
        return 'due_soon'
    return 'upcoming'


def summarize(grants):
    totals = {}
    for grant in grants:
        currency = grant['currency']
        group = totals.setdefault(currency, dict(currency=currency, awarded=Decimal(0), allocated=Decimal(0), spent=Decimal(0), remaining=Decimal(0)))
        group['awarded'] += grant['award_amount']
        group['allocated'] += grant['allocated']
        group['spent'] += grant['spent']
        group['remaining'] += grant['award_amount'] - grant['spent']
    return list(totals.values())
