-- Fictional development data. Run once after provisioning at least one active staff member.
-- Transactional: if any insert fails, no partial seed is committed.
BEGIN;
DO $$
DECLARE staff uuid; donor uuid; grant_id uuid; category uuid; metric uuid;
BEGIN
  SELECT user_id INTO staff FROM private.staff_members WHERE is_active ORDER BY created_at LIMIT 1;
  IF staff IS NULL THEN RAISE EXCEPTION 'Provision an active staff member before seeding'; END IF;
  INSERT INTO private.donors(name,contact_email) VALUES('Fictional Cedar Foundation','grants@cedar.example') RETURNING id INTO donor;
  INSERT INTO private.grants(donor_id,name,award_amount,currency,start_date,end_date,status)
    VALUES(donor,'Community Meals Pilot',50000,'USD',current_date-30,current_date+335,'active') RETURNING id INTO grant_id;
  INSERT INTO private.budget_categories(grant_id,name,allocated_amount) VALUES(grant_id,'Meal supplies',30000) RETURNING id INTO category;
  INSERT INTO private.budget_categories(grant_id,name,allocated_amount) VALUES(grant_id,'Volunteer transport',10000);
  INSERT INTO private.expenses(budget_category_id,amount,expense_date,description,created_by)
    VALUES(category,1250.50,current_date-2,'Fictional pantry purchase',staff);
  INSERT INTO private.reporting_deadlines(grant_id,title,due_date) VALUES(grant_id,'First progress report',current_date+7),(grant_id,'Initial activity summary',current_date-2);
  INSERT INTO private.impact_metrics(grant_id,name,unit,target_value) VALUES(grant_id,'Meals served','meals',10000) RETURNING id INTO metric;
  INSERT INTO private.impact_updates(impact_metric_id,period_start,period_end,actual_value,created_by)
    VALUES(metric,current_date-28,current_date-1,420,staff);
END $$;
COMMIT;
