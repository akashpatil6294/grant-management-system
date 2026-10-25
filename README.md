# Grantwise — Grant Management MVP

A single-nonprofit workspace for authenticated staff to manage donors, grants, budgets, expenses, reporting deadlines, and additive impact outcomes. React + TypeScript + Vite + Tailwind + Recharts, backed by FastAPI and Supabase PostgreSQL/Auth.

This is the first development slice, not a production release. No credentials are included. The application does not display fictional data as live data or offer an authentication bypass.

## What is implemented

- Supabase email/password sign-in and sign-out; every business API request verifies the token with Supabase Auth and checks active staff membership.
- Donor creation, listing, viewing through the API, and editing.
- Grant creation, listing, detail view, and editing.
- Budget allocation and editing, expense recording and editing, decimal-safe balances.
- PostgreSQL constraints and transaction locks that reject allocations above the award, expenses above the category balance, and reductions below existing spending. Currency cannot change after budget allocation. Closed grants reject financial changes.
- Dashboard with donor filter, per-currency totals, expenditure chart, deadline alerts, and impact outcomes.
- Reporting deadlines with submitted status, overdue alerts, and a 14-day upcoming window.
- Additive outcome targets, period-based impact entries, and history. Overlapping periods are rejected.
- Input validation, loading/empty/error states, and safe API/database error messages.

All active staff have the same permissions. There is no donor login, payment processing, receipt upload, email reminder service, immutable audit trail, or multi-organization support yet.

## Project layout

```text
frontend/src/
  api/client.ts          Authenticated API calls, pagination and errors
  components/           Reusable editor and table
  features/             Dashboard and grant detail workspace
  lib/                  Supabase Auth and decimal formatting
  App.tsx               Login, navigation, donors and grants
backend/app/
  main.py               API routes and safe database errors
  auth.py               Supabase verification and staff membership
  schemas.py            Validated request models
  services.py           Database helpers and reporting calculations
  database.py           Transaction-scoped connections
  config.py             Environment configuration
backend/tests/          Unit/access-control and API integration tests
database/
  migrations/           Versioned SQL schema
  backend_role.sql      Restricted database role
  seed.sql              Fictional development records
  tests/                Isolated PostgreSQL tests and API test runner
docs/                   Design and verification notes
```

## Prerequisites

- Python 3.11+ and Node.js 22.12+ (tested locally with Python 3.11 and Node 24).
- A Supabase project with PostgreSQL and email/password Auth enabled.
- PowerShell commands below assume you start in this repository. Use `npm.cmd` on Windows to avoid PowerShell script policy issues. macOS/Linux users can use `npm` and `.venv/bin/python` instead.

## 1. Set up Supabase

1. Open the project's SQL editor as the database owner. Run `database/migrations/001_initial.sql` **once**. It creates the `private` schema; do not add this schema to Supabase's exposed API schemas.
2. Run `database/backend_role.sql` **once**. Set a strong password separately in the SQL editor using `ALTER ROLE grant_api PASSWORD 'your-generated-password';`. Do not save the real statement in the repository.
3. In Supabase Authentication → Users, create a staff user with an email and password. Complete email confirmation or create an email-confirmed user through the admin interface. Disable public sign-ups if they are not needed.
4. Copy that user's UUID and provision membership in the SQL editor:

```sql
INSERT INTO private.staff_members (user_id, display_name)
VALUES ('REPLACE_WITH_AUTH_USER_UUID', 'Your staff name');
```

5. Optionally run `database/seed.sql` once in a development project. It requires an active staff member and adds a fictional foundation, grant, categories, expense, deadlines, and impact data. Re-running it adds another fictional dataset.
6. Obtain the project URL and **publishable key** from Supabase. Never put a service-role key or database password in the frontend.
7. Obtain a PostgreSQL connection URI from Supabase Connect. Use `grant_api` as the database user and its password. For the Supabase pooler, the username generally includes the project reference (`grant_api.PROJECT_REF`); use the host and port shown by Connect. Prefer the direct or session-pooler connection for this initial version. Keep TLS enabled (`sslmode=require`) and URL-encode special characters in passwords.

The restricted role can read staff membership but cannot provision staff, delete records, or read `auth.users`. Migrations and staff provisioning must use an administrator account, never the application's database role.

## 2. Install and run the backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres?sslmode=require
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_SUPABASE_PUBLISHABLE_KEY
FRONTEND_ORIGIN=http://localhost:5173
APP_TIMEZONE=Asia/Calcutta
```

Start from the `backend` folder so `.env` is loaded:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API documentation: <http://localhost:8000/docs>
- Process health: <http://localhost:8000/health>
- Database readiness: <http://localhost:8000/ready>

`/health` does not prove that Supabase is configured; `/ready` queries the migrated database. Missing configuration returns an actionable `503`. No live Supabase connection was available during development verification.

## 3. Install and run the frontend

Open another terminal at the repository root:

```powershell
cd frontend
npm.cmd ci
Copy-Item .env.example .env
```

Edit `frontend/.env` with the same Supabase project URL and publishable key:

```dotenv
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_SUPABASE_PUBLISHABLE_KEY
```

```powershell
npm.cmd run dev -- --host 127.0.0.1
```

Open <http://localhost:5173> and sign in with the provisioned staff account. Keep the browser origin consistent with `FRONTEND_ORIGIN`; `localhost` and `127.0.0.1` are different origins. Restart Vite after changing its environment file. Environment examples contain placeholders, not working credentials.

The frontend accepts either `VITE_SUPABASE_PUBLISHABLE_KEY` or `VITE_SUPABASE_ANON_KEY`; the publishable setting takes precedence when both are present. The backend uses psycopg directly: `DATABASE_URL` must contain only the `postgresql://...` URI, without a repeated `DATABASE_URL=` prefix or a `+psycopg` driver suffix.

## 4. Run tests and builds

Backend unit, validation and access-control tests, from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q
```

Frontend decimal tests and production build, from `frontend`:

```powershell
npm.cmd test
npm.cmd run build
```

Database constraint tests and full API workflow, from `database`:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run test:api
```

These database tests use PGlite (embedded PostgreSQL) in memory. The API test runner starts a loopback-only database on port 55439 and uses `backend/.venv` to run Python tests. Set `TEST_DATABASE_PORT` if the port is occupied, or `TEST_PYTHON` to use a different Python executable. It creates an isolated `auth.users` FK target and overrides authentication **only in pytest**. It does not contact Supabase or modify your configured database. Plain `pytest` skips the integration test unless launched by this runner.

PGlite does not reproduce a multi-connection production PostgreSQL server. Concurrent-write behavior, live Supabase sign-in and actual project permissions need a staging test before production use. See `docs/verification.md` for the checks actually executed.

## Manual acceptance walkthrough after Supabase setup

1. Sign in as a provisioned staff user. Confirm an unprovisioned user receives an access error.
2. Create a donor and a USD 100 grant. Edit both, then open the grant.
3. Allocate USD 80. Try allocating another USD 20.01: expect rejection.
4. Record USD 0.10 and USD 0.20 expenses. Confirm spent is USD 0.30. Try another USD 79.71 expense: expect rejection.
5. Add a report due yesterday, inspect the dashboard alert, then mark it submitted and confirm the alert disappears.
6. Add a meals-served target and record one reporting period. Try an overlapping period: expect rejection.
7. Add a grant in a different currency and confirm dashboard totals remain separate.
8. Sign out and confirm the workspace is no longer accessible.

## API conventions and financial rules

- `/api/me`, `/api/donors`, `/api/grants`, `/api/dashboard` and nested grant resources are documented in FastAPI's `/docs`.
- `PATCH` currently accepts the **complete editable form**, not an arbitrary partial JSON object. Omitted optional fields use their defaults. The frontend submits complete forms.
- Donor/grant/expense lists use `limit` (1–500) and `offset`. The frontend loads all pages for this small initial workspace.
- Monetary values travel as decimal strings, use Python `Decimal`, and are stored as `NUMERIC(14,2)`. The frontend uses `decimal.js` for financial arithmetic. Chart geometry uses approximate numbers; exact values remain in financial tables.
- Award remaining = award − expenses. Unallocated = award − allocations. Category available = allocation − category expenses.
- Financial mutations lock the parent grant before changing data. Database triggers enforce the same financial constraints. Parent grant/category relationships are immutable.
- Deadlines are date-based in `APP_TIMEZONE`; submission timestamps are stored in UTC.
- Impact metrics are additive quantities only. Unique beneficiaries and percentages need different aggregation rules and are not supported yet.
- There is no record deletion API. Financial edits are supported, but an immutable audit ledger is future work.

## Troubleshooting

- **403 after sign-in:** check that the Auth user UUID has an active row in `private.staff_members`.
- **Database 503:** check connection URI, TLS, network reachability, role password, grants, and migration installation. Raw database errors are intentionally hidden from clients.
- **CORS error:** align `FRONTEND_ORIGIN` with the browser URL and restart FastAPI.
- **Dependency certificate error on a managed Windows computer:** use an up-to-date pip with system certificate support. Node 24 can use `$env:NODE_USE_SYSTEM_CA='1'` before `npm.cmd ci`. Do not disable TLS verification.
- **Tests stall in a restricted runner:** FastAPI's test client needs local socket access on Windows, even for in-process requests. Run tests in a normal terminal with loopback access.

## Next development slice

Live Supabase/staging acceptance, real PostgreSQL concurrency tests, browser end-to-end tests, accessibility refinement, audit history, impact-entry corrections, email reminders, exportable donor reports, and deployment configuration. The initial API uses small router/service modules and direct parameterized SQL; an ORM, queue, and microservices are intentionally unnecessary at this stage.

Implementation references: [Supabase user verification](https://supabase.com/docs/reference/python/auth-getuser), [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite), and [PGlite socket test adapter](https://pglite.dev/docs/pglite-socket).
