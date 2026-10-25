BEGIN;
CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;

CREATE TABLE private.staff_members (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE RESTRICT,
  display_name text NOT NULL CHECK (length(trim(display_name)) BETWEEN 1 AND 160),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE private.donors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 160),
  contact_email text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE private.grants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  donor_id uuid NOT NULL REFERENCES private.donors(id) ON DELETE RESTRICT,
  name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 160),
  award_amount numeric(14,2) NOT NULL CHECK (award_amount > 0),
  currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  start_date date NOT NULL, end_date date NOT NULL CHECK (end_date >= start_date),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','closed')),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE private.budget_categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  grant_id uuid NOT NULL REFERENCES private.grants(id) ON DELETE RESTRICT,
  name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 160),
  allocated_amount numeric(14,2) NOT NULL CHECK (allocated_amount >= 0),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX category_name_unique ON private.budget_categories (grant_id, lower(name));
CREATE TABLE private.expenses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  budget_category_id uuid NOT NULL REFERENCES private.budget_categories(id) ON DELETE RESTRICT,
  amount numeric(14,2) NOT NULL CHECK (amount > 0), expense_date date NOT NULL,
  description text NOT NULL CHECK (length(trim(description)) BETWEEN 1 AND 2000), reference text,
  created_by uuid NOT NULL REFERENCES private.staff_members(user_id),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX expenses_category_idx ON private.expenses(budget_category_id);
CREATE INDEX grants_donor_idx ON private.grants(donor_id);
CREATE TABLE private.reporting_deadlines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  grant_id uuid NOT NULL REFERENCES private.grants(id) ON DELETE RESTRICT,
  title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 160),
  due_date date NOT NULL, submitted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX deadlines_grant_idx ON private.reporting_deadlines(grant_id);
CREATE INDEX deadlines_due_idx ON private.reporting_deadlines(due_date) WHERE submitted_at IS NULL;
CREATE TABLE private.impact_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  grant_id uuid NOT NULL REFERENCES private.grants(id) ON DELETE RESTRICT,
  name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 160),
  unit text NOT NULL CHECK (length(trim(unit)) BETWEEN 1 AND 160),
  target_value numeric(14,2) NOT NULL CHECK (target_value > 0),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX metric_name_unique ON private.impact_metrics(grant_id,lower(name));
CREATE TABLE private.impact_updates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  impact_metric_id uuid NOT NULL REFERENCES private.impact_metrics(id) ON DELETE RESTRICT,
  period_start date NOT NULL, period_end date NOT NULL CHECK (period_end >= period_start),
  actual_value numeric(14,2) NOT NULL CHECK (actual_value >= 0), notes text,
  created_by uuid NOT NULL REFERENCES private.staff_members(user_id),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX impact_updates_metric_idx ON private.impact_updates(impact_metric_id);

-- A single grant row is the transaction lock for every budget mutation.
-- Parent relationships are immutable, avoiding cross-grant lock ordering problems.
CREATE FUNCTION private.check_budget() RETURNS trigger LANGUAGE plpgsql SET search_path = private, pg_temp AS $$
DECLARE gid uuid; award numeric; allocated numeric; spent numeric; category_limit numeric; grant_status text;
BEGIN
  IF TG_TABLE_NAME = 'grants' THEN
    IF TG_OP = 'UPDATE' THEN
      IF NEW.currency <> OLD.currency AND EXISTS(SELECT 1 FROM budget_categories WHERE grant_id=NEW.id) THEN
        RAISE EXCEPTION 'Currency cannot change after allocating funds' USING ERRCODE='23514';
      END IF;
      SELECT coalesce(sum(allocated_amount),0) INTO allocated FROM budget_categories WHERE grant_id=NEW.id;
      IF NEW.award_amount < allocated THEN
        RAISE EXCEPTION 'Award cannot be less than allocated funds' USING ERRCODE='23514';
      END IF;
    END IF;
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME = 'budget_categories' THEN
    IF TG_OP = 'UPDATE' AND NEW.grant_id <> OLD.grant_id THEN
      RAISE EXCEPTION 'Category grant cannot change' USING ERRCODE='23514';
    END IF;
    gid := NEW.grant_id;
  ELSE
    IF TG_OP = 'UPDATE' AND NEW.budget_category_id <> OLD.budget_category_id THEN
      RAISE EXCEPTION 'Expense category cannot change' USING ERRCODE='23514';
    END IF;
    SELECT grant_id INTO gid FROM budget_categories WHERE id=NEW.budget_category_id;
  END IF;
  SELECT award_amount, status INTO award, grant_status FROM grants WHERE id=gid FOR UPDATE;
  IF grant_status='closed' THEN
    RAISE EXCEPTION 'Closed grants cannot receive budget or expense changes' USING ERRCODE='23514';
  END IF;
  IF TG_TABLE_NAME='budget_categories' THEN
    SELECT coalesce(sum(allocated_amount),0) INTO allocated FROM budget_categories WHERE grant_id=gid AND id<>NEW.id;
    IF allocated + NEW.allocated_amount > award THEN
      RAISE EXCEPTION 'Allocations exceed the grant award' USING ERRCODE='23514';
    END IF;
    SELECT coalesce(sum(amount),0) INTO spent FROM expenses WHERE budget_category_id=NEW.id;
    IF NEW.allocated_amount < spent THEN
      RAISE EXCEPTION 'Allocation cannot be less than recorded spending' USING ERRCODE='23514';
    END IF;
  ELSE
    SELECT allocated_amount INTO category_limit FROM budget_categories WHERE id=NEW.budget_category_id;
    SELECT coalesce(sum(amount),0) INTO spent FROM expenses WHERE budget_category_id=NEW.budget_category_id AND id<>NEW.id;
    IF spent + NEW.amount > category_limit THEN
      RAISE EXCEPTION 'Expense exceeds the category balance' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER grant_budget_check BEFORE UPDATE ON private.grants FOR EACH ROW EXECUTE FUNCTION private.check_budget();
CREATE TRIGGER category_budget_check BEFORE INSERT OR UPDATE ON private.budget_categories FOR EACH ROW EXECUTE FUNCTION private.check_budget();
CREATE TRIGGER expense_budget_check BEFORE INSERT OR UPDATE ON private.expenses FOR EACH ROW EXECUTE FUNCTION private.check_budget();

CREATE FUNCTION private.check_impact_period() RETURNS trigger LANGUAGE plpgsql SET search_path=private,pg_temp AS $$
BEGIN
  IF TG_OP='UPDATE' AND NEW.impact_metric_id<>OLD.impact_metric_id THEN
    RAISE EXCEPTION 'Metric cannot change' USING ERRCODE='23514';
  END IF;
  PERFORM 1 FROM impact_metrics WHERE id=NEW.impact_metric_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM impact_updates WHERE impact_metric_id=NEW.impact_metric_id AND id<>NEW.id
    AND period_start<=NEW.period_end AND period_end>=NEW.period_start) THEN
    RAISE EXCEPTION 'Impact reporting periods must not overlap' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER impact_period_check BEFORE INSERT OR UPDATE ON private.impact_updates FOR EACH ROW EXECUTE FUNCTION private.check_impact_period();

CREATE FUNCTION private.touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at=now(); RETURN NEW; END $$;
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['donors','grants','budget_categories','expenses','reporting_deadlines','impact_metrics','impact_updates'] LOOP
    EXECUTE format('CREATE TRIGGER updated_at BEFORE UPDATE ON private.%I FOR EACH ROW EXECUTE FUNCTION private.touch_updated_at()',t);
  END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA private FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA private FROM PUBLIC;
COMMIT;
