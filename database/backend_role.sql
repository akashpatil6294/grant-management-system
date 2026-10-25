-- Run as the migration owner after 001_initial.sql.
-- Supply the password separately in the Supabase SQL editor; never save it in this file.
CREATE ROLE grant_api LOGIN;
GRANT USAGE ON SCHEMA private TO grant_api;
GRANT SELECT ON ALL TABLES IN SCHEMA private TO grant_api;
GRANT INSERT, UPDATE ON private.donors, private.grants, private.budget_categories,
  private.expenses, private.reporting_deadlines, private.impact_metrics, private.impact_updates TO grant_api;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA private TO grant_api;
-- grant_api intentionally cannot create staff, delete financial records, or access auth.users.
