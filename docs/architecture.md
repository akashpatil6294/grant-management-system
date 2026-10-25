# Architecture and data relationships

React communicates with FastAPI for all business data. Supabase JS handles sign-in and session refresh only. FastAPI validates bearer tokens against the configured Supabase Auth server and checks `private.staff_members.is_active` for every request.

The backend connects with a restricted PostgreSQL login. The private schema is not exposed through Supabase's data API. Only an administrator can provision staff. All staff can manage all records for one nonprofit.

Relationships:

```text
auth.users → staff_members → expenses / impact_updates (created_by)
donors → grants → budget_categories → expenses
               → reporting_deadlines
               → impact_metrics → impact_updates
```

The migration is the schema source of truth. PostgreSQL foreign keys prevent orphaned records; unique indexes constrain category and outcome names within a grant. There are no cached balance columns. Dashboard SQL aggregates expenses independently from allocations to avoid multiplying totals through joins.

Each financial API transaction acquires a lock on its parent grant before insert/update. All APIs acquire the grant lock first, including category edits and award reductions. Database triggers reject invalid budgets, currency changes after allocation, and writes to closed grants. Expense-category and category-grant relationships cannot move. Impact writes lock their metric before checking period overlaps.

The dashboard uses a repeatable-read transaction for a consistent view across its queries. Multiple currencies are never summed together. All currency amounts currently use two fractional digits; currencies requiring another precision are outside this MVP.

Scope choices: direct psycopg SQL instead of an ORM; full-form PATCH models; local dashboard alerts instead of a worker; no destructive operations; no public donor portal. These keep the first development slice small. The database migrations and API contracts can support later router extraction, audit history and deployment work without introducing additional services now.
