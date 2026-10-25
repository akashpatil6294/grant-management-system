import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .auth import current_staff
from .config import settings
from .database import connection
from .schemas import Donor, Grant, Category, Expense, Deadline, Metric, ImpactUpdate
from .services import one, save, lock_grant, deadline_status, summarize

app = FastAPI(title='Grant Management API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=[settings().frontend_origin],
                   allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Authorization', 'Content-Type'])


def result(data, status=200):
    # Preserve decimal values as strings through JSON transport.
    return JSONResponse(jsonable_encoder(data, custom_encoder={Decimal: str}), status_code=status)


@app.exception_handler(psycopg.Error)
async def database_error(request, exc):
    # SQLSTATE and exception type diagnose server/client failures without exposing
    # passwords, connection strings, SQL parameters, or database row contents.
    logging.getLogger(__name__).error(
        'Database operation failed: type=%s sqlstate=%s',
        type(exc).__name__, exc.sqlstate or 'none',
    )
    if isinstance(exc, (psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName)):
        return result({'detail': 'Database tables are missing. Apply the application migration to the Supabase project configured in Render.'}, 503)
    if isinstance(exc, psycopg.errors.InsufficientPrivilege):
        return result({'detail': 'The database account lacks application permissions. Check the backend role grants in Supabase.'}, 503)
    if isinstance(exc, psycopg.errors.CheckViolation):
        # Only our trigger messages are safe to expose; never return SQL or row details.
        message = exc.diag.message_primary or ''
        safe = ('Allocations exceed', 'Expense exceeds', 'Award cannot', 'Allocation cannot',
                'Currency cannot', 'Closed grants', 'Impact reporting', 'Category grant', 'Expense category', 'Metric cannot')
        return result({'detail': message if message.startswith(safe) else 'The record violates a data constraint.'}, 409)
    if isinstance(exc, psycopg.errors.UniqueViolation):
        return result({'detail': 'A record with this name already exists for this grant.'}, 409)
    if isinstance(exc, psycopg.errors.ForeignKeyViolation):
        return result({'detail': 'A referenced record does not exist.'}, 422)
    if isinstance(exc, (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure)):
        return result({'detail': 'Another update conflicted with this one. Refresh and try again.'}, 409)
    return result({'detail': 'Database is unavailable. Please try again.'}, 503)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/ready')
def ready():
    with connection() as conn:
        conn.execute('SELECT 1 FROM private.grants LIMIT 1')
    return {'status': 'ready'}


@app.get('/api/me')
def me(staff=Depends(current_staff)):
    return result(staff)


@app.get('/api/donors')
def donors(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), staff=Depends(current_staff)):
    with connection() as conn:
        return result(conn.execute('SELECT * FROM donors ORDER BY name,id LIMIT %s OFFSET %s', (limit, offset)).fetchall())


@app.post('/api/donors', status_code=201)
def create_donor(body: Donor, staff=Depends(current_staff)):
    with connection() as conn:
        return result(save(conn, 'donors', body.model_dump()), 201)


@app.get('/api/donors/{record_id}')
def donor(record_id: UUID, staff=Depends(current_staff)):
    with connection() as conn:
        return result(one(conn, 'donors', record_id))


@app.patch('/api/donors/{record_id}')
def edit_donor(record_id: UUID, body: Donor, staff=Depends(current_staff)):
    with connection() as conn:
        return result(save(conn, 'donors', body.model_dump(), record_id))


GRANT_SELECT = '''SELECT g.*, d.name AS donor_name,
  coalesce((SELECT sum(allocated_amount) FROM budget_categories WHERE grant_id=g.id),0) AS allocated,
  coalesce((SELECT sum(e.amount) FROM expenses e JOIN budget_categories b ON b.id=e.budget_category_id WHERE b.grant_id=g.id),0) AS spent
  FROM grants g JOIN donors d ON d.id=g.donor_id'''


@app.get('/api/grants')
def grants(donor_id: UUID | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), staff=Depends(current_staff)):
    with connection() as conn:
        return result(conn.execute(GRANT_SELECT + ' WHERE (%s::uuid IS NULL OR g.donor_id=%s) ORDER BY g.created_at DESC,g.id LIMIT %s OFFSET %s',
                                   (donor_id, donor_id, limit, offset)).fetchall())


@app.post('/api/grants', status_code=201)
def create_grant(body: Grant, staff=Depends(current_staff)):
    with connection() as conn:
        return result(save(conn, 'grants', body.model_dump()), 201)


@app.get('/api/grants/{record_id}')
def grant(record_id: UUID, staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'grants', record_id)
        return result(conn.execute(GRANT_SELECT + ' WHERE g.id=%s', (record_id,)).fetchone())


@app.patch('/api/grants/{record_id}')
def edit_grant(record_id: UUID, body: Grant, staff=Depends(current_staff)):
    with connection() as conn:
        lock_grant(conn, record_id)
        return result(save(conn, 'grants', body.model_dump(), record_id))


@app.get('/api/grants/{grant_id}/budget-categories')
def categories(grant_id: UUID, staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'grants', grant_id)
        return result(conn.execute('SELECT b.*, coalesce((SELECT sum(amount) FROM expenses WHERE budget_category_id=b.id),0) AS spent FROM budget_categories b WHERE grant_id=%s ORDER BY name,id', (grant_id,)).fetchall())


@app.post('/api/grants/{grant_id}/budget-categories', status_code=201)
def create_category(grant_id: UUID, body: Category, staff=Depends(current_staff)):
    with connection() as conn:
        lock_grant(conn, grant_id)
        return result(save(conn, 'budget_categories', {**body.model_dump(), 'grant_id': grant_id}), 201)


@app.patch('/api/budget-categories/{record_id}')
def edit_category(record_id: UUID, body: Category, staff=Depends(current_staff)):
    with connection() as conn:
        category = one(conn, 'budget_categories', record_id)
        lock_grant(conn, category['grant_id'])
        return result(save(conn, 'budget_categories', body.model_dump(), record_id))


@app.get('/api/grants/{grant_id}/expenses')
def expenses(grant_id: UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'grants', grant_id)
        return result(conn.execute('SELECT e.*, b.name AS category_name FROM expenses e JOIN budget_categories b ON b.id=e.budget_category_id WHERE b.grant_id=%s ORDER BY expense_date DESC,e.id LIMIT %s OFFSET %s', (grant_id, limit, offset)).fetchall())


@app.post('/api/grants/{grant_id}/expenses', status_code=201)
def create_expense(grant_id: UUID, body: Expense, staff=Depends(current_staff)):
    with connection() as conn:
        lock_grant(conn, grant_id)
        category = one(conn, 'budget_categories', body.budget_category_id)
        if category['grant_id'] != grant_id:
            raise HTTPException(422, 'Category belongs to a different grant.')
        return result(save(conn, 'expenses', {**body.model_dump(), 'created_by': staff['user_id']}), 201)


@app.patch('/api/expenses/{record_id}')
def edit_expense(record_id: UUID, body: Expense, staff=Depends(current_staff)):
    with connection() as conn:
        existing = one(conn, 'expenses', record_id)
        category = one(conn, 'budget_categories', existing['budget_category_id'])
        lock_grant(conn, category['grant_id'])
        return result(save(conn, 'expenses', body.model_dump(), record_id))


def today():
    return datetime.now(ZoneInfo(settings().app_timezone)).date()


def annotate_deadlines(rows):
    for row in rows:
        row['status'] = deadline_status(row['due_date'], row['submitted_at'], today())
    return rows


@app.get('/api/grants/{grant_id}/reporting-deadlines')
def deadlines(grant_id: UUID, staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'grants', grant_id)
        return result(annotate_deadlines(conn.execute('SELECT * FROM reporting_deadlines WHERE grant_id=%s ORDER BY due_date,id', (grant_id,)).fetchall()))


@app.post('/api/grants/{grant_id}/reporting-deadlines', status_code=201)
def create_deadline(grant_id: UUID, body: Deadline, staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'grants', grant_id)
        data = body.model_dump(exclude={'submitted'})
        data.update(grant_id=grant_id, submitted_at=datetime.now(ZoneInfo('UTC')) if body.submitted else None)
        return result(save(conn, 'reporting_deadlines', data), 201)


@app.patch('/api/reporting-deadlines/{record_id}')
def edit_deadline(record_id: UUID, body: Deadline, staff=Depends(current_staff)):
    with connection() as conn:
        old = one(conn, 'reporting_deadlines', record_id)
        data = body.model_dump(exclude={'submitted'})
        data['submitted_at'] = (old['submitted_at'] or datetime.now(ZoneInfo('UTC'))) if body.submitted else None
        return result(save(conn, 'reporting_deadlines', data, record_id))


@app.get('/api/grants/{grant_id}/impact-metrics')
def metrics(grant_id: UUID, staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'grants', grant_id)
        return result(conn.execute('SELECT m.*, coalesce((SELECT sum(actual_value) FROM impact_updates WHERE impact_metric_id=m.id),0) AS actual_value FROM impact_metrics m WHERE grant_id=%s ORDER BY name,id', (grant_id,)).fetchall())


@app.post('/api/grants/{grant_id}/impact-metrics', status_code=201)
def create_metric(grant_id: UUID, body: Metric, staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'grants', grant_id)
        return result(save(conn, 'impact_metrics', {**body.model_dump(), 'grant_id': grant_id}), 201)


@app.patch('/api/impact-metrics/{record_id}')
def edit_metric(record_id: UUID, body: Metric, staff=Depends(current_staff)):
    with connection() as conn:
        return result(save(conn, 'impact_metrics', body.model_dump(), record_id))


@app.get('/api/impact-metrics/{metric_id}/updates')
def updates(metric_id: UUID, staff=Depends(current_staff)):
    with connection() as conn:
        one(conn, 'impact_metrics', metric_id)
        return result(conn.execute('SELECT * FROM impact_updates WHERE impact_metric_id=%s ORDER BY period_start,id', (metric_id,)).fetchall())


@app.post('/api/impact-metrics/{metric_id}/updates', status_code=201)
def create_update(metric_id: UUID, body: ImpactUpdate, staff=Depends(current_staff)):
    with connection() as conn:
        if not conn.execute('SELECT id FROM impact_metrics WHERE id=%s FOR UPDATE', (metric_id,)).fetchone():
            raise HTTPException(404, 'Metric not found.')
        return result(save(conn, 'impact_updates', {**body.model_dump(), 'impact_metric_id': metric_id, 'created_by': staff['user_id']}), 201)


@app.get('/api/dashboard')
def dashboard(donor_id: UUID | None = None, grant_id: UUID | None = None, staff=Depends(current_staff)):
    with connection() as conn:
        # A consistent snapshot across financial and reporting queries.
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        rows = conn.execute(GRANT_SELECT + ' WHERE (%s::uuid IS NULL OR g.donor_id=%s) AND (%s::uuid IS NULL OR g.id=%s) ORDER BY g.name,g.id', (donor_id, donor_id, grant_id, grant_id)).fetchall()
        ids = [r['id'] for r in rows]
        reports = annotate_deadlines(conn.execute('SELECT r.*,g.name AS grant_name FROM reporting_deadlines r JOIN grants g ON g.id=r.grant_id WHERE r.grant_id=ANY(%s::uuid[]) ORDER BY r.due_date,r.id', (ids,)).fetchall())
        impact = conn.execute('SELECT m.*, g.name AS grant_name, coalesce((SELECT sum(actual_value) FROM impact_updates WHERE impact_metric_id=m.id),0) AS actual_value FROM impact_metrics m JOIN grants g ON g.id=m.grant_id WHERE m.grant_id=ANY(%s::uuid[]) ORDER BY m.name,m.id', (ids,)).fetchall()
        return result({'grant_count': len(rows), 'totals': summarize(rows), 'grants': rows, 'deadlines': reports, 'impact': impact})
