# Verification record — 25 October 2026

## Executed successfully

| Component | Command (from its folder) | Result |
|---|---|---|
| Backend | `.venv/Scripts/python.exe -m pytest tests/test_app.py -q` | 31 passed |
| Database | `npm.cmd test` | 10 passed |
| API integration | `npm.cmd run test:api` | 1 passed; a multi-step workflow against an isolated PostgreSQL-compatible PGlite database |
| Frontend | `npm.cmd test` | 3 passed |
| Frontend | `npm.cmd run build` | TypeScript validation and Vite production build passed |
| Dependencies | frontend installation after updating Vitest to 5.0.5 | npm audit reported 0 vulnerabilities |
| Dependencies | database installation with PGlite 0.5.11/socket 0.2.14 | npm audit reported 0 vulnerabilities |

Backend checks cover protected routes, rejected invalid sessions, inactive/missing membership, successful staff verification with a mocked Auth response, Auth provider failures, invalid dates/email/amounts, decimal-safe serialization, and currency-separated totals. Network calls to Supabase are mocked in these tests.

Database checks execute the actual migration, triggers, fictional seed and role grants. They cover exact numeric sums, overspending, over-allocation, award/allocation reductions, currency changes, duplicate categories, overlapping impact periods, dependent-record protection, closed grants and denied access for the restricted role.

The API integration test performs donor/grant creation and editing, viewing/filtering, budget creation, expense recording/editing, financial rejection cases, report submission, impact recording and overlap rejection, dashboard aggregation, expense pagination, a missing-resource response and closed-grant enforcement. Authentication is overridden only inside the test. SQL and psycopg communication are real; this is not a mocked repository test.

## Failures encountered and resolved

- Initial dependency installs were blocked by network/certificate restrictions. Retried with approved network access and system certificate support; TLS verification was not disabled.
- Initial FastAPI test runs stalled because the restricted Windows environment blocked asyncio's local socket pair. The same tests passed with local networking available.
- Initial frontend build failed on a nullable Supabase reference in the sign-out callback. Fixed the narrowed reference and reran the build successfully.
- Initial test-adapter install had incompatible PGlite peer versions. Installed matching versions and reran database/API tests successfully.
- Initial frontend dependency audit found three vulnerabilities in the old test-runner dependency tree. Updated Vitest to 5.0.5; install audit returned zero vulnerabilities and tests passed.

## Warning still present

The Python test client emits a Starlette deprecation warning about its httpx adapter. All assertions pass. This is a test-client compatibility warning, not a verified application failure.

## Not verified

- No Supabase credentials were supplied. No remote migration, real Auth sign-in/session refresh, live API request to Supabase, or restricted-role connection to an actual Supabase project was performed.
- Docker's database engine was unavailable. PGlite tests do not establish correctness under true multi-connection PostgreSQL concurrency. Verify simultaneous expense/allocation writes on staging before deployment.
- Browser rendering, responsive layouts, keyboard/focus behavior, and end-to-end browser interactions have not been tested. Frontend checks currently cover compilation and decimal calculations.
- Production deployment, load testing, backup/restore, email delivery, and financial audit history are outside this development slice.

No claim of production readiness or live Supabase functionality is made.
