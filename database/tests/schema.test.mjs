import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';

let db;
const staff = '00000000-0000-0000-0000-000000000001';
let donor, grant, category, metric;
const row = async (sql, params=[]) => (await db.query(sql,params)).rows[0];
before(async () => {
  db = new PGlite();
  // Supabase owns auth.users in production. Only its FK target is stubbed here.
  await db.exec('CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);');
  await db.exec(await readFile(new URL('../migrations/001_initial.sql',import.meta.url),'utf8'));
  await db.query('INSERT INTO auth.users VALUES ($1)',[staff]);
  await db.query("INSERT INTO private.staff_members(user_id,display_name) VALUES($1,'Test staff')",[staff]);
  donor = (await row("INSERT INTO private.donors(name) VALUES('Test foundation') RETURNING id")).id;
  grant = (await row("INSERT INTO private.grants(donor_id,name,award_amount,currency,start_date,end_date,status) VALUES($1,'Test grant',100,'USD','2026-01-01','2026-12-31','active') RETURNING id",[donor])).id;
  category = (await row("INSERT INTO private.budget_categories(grant_id,name,allocated_amount) VALUES($1,'Supplies',60) RETURNING id",[grant])).id;
  metric = (await row("INSERT INTO private.impact_metrics(grant_id,name,unit,target_value) VALUES($1,'Meals','meals',100) RETURNING id",[grant])).id;
});
after(async () => { await db?.close(); });

test('migration creates all eight application tables',async () => {
  assert.equal(Number((await row("SELECT count(*) AS count FROM information_schema.tables WHERE table_schema='private'")).count),8);
});
test('allocation cannot exceed grant award',async () => {
  await assert.rejects(db.query("INSERT INTO private.budget_categories(grant_id,name,allocated_amount) VALUES($1,'Excess',40.01)",[grant]),/Allocations exceed/);
});
test('expense arithmetic is exact; overspending and reducing allocations are rejected',async () => {
  await db.query("INSERT INTO private.expenses(budget_category_id,amount,expense_date,description,created_by) VALUES($1,0.10,'2026-01-01','First',$2),($1,0.20,'2026-01-01','Second',$2)",[category,staff]);
  assert.equal((await row('SELECT sum(amount)::text AS spent FROM private.expenses WHERE budget_category_id=$1',[category])).spent,'0.30');
  await assert.rejects(db.query("INSERT INTO private.expenses(budget_category_id,amount,expense_date,description,created_by) VALUES($1,59.71,'2026-01-01','Too much',$2)",[category,staff]),/Expense exceeds/);
  await assert.rejects(db.query('UPDATE private.budget_categories SET allocated_amount=0.29 WHERE id=$1',[category]),/Allocation cannot/);
});
test('award reduction and currency change are rejected after allocation',async () => {
  await assert.rejects(db.query('UPDATE private.grants SET award_amount=59 WHERE id=$1',[grant]),/Award cannot/);
  await assert.rejects(db.query("UPDATE private.grants SET currency='INR' WHERE id=$1",[grant]),/Currency cannot/);
});
test('category names are unique ignoring case',async () => {
  await assert.rejects(db.query("INSERT INTO private.budget_categories(grant_id,name,allocated_amount) VALUES($1,'supplies',1)",[grant]),/duplicate key/);
});
test('impact periods reject overlap including shared boundary day',async () => {
  await db.query("INSERT INTO private.impact_updates(impact_metric_id,period_start,period_end,actual_value,created_by) VALUES($1,'2026-01-01','2026-01-07',10,$2)",[metric,staff]);
  await assert.rejects(db.query("INSERT INTO private.impact_updates(impact_metric_id,period_start,period_end,actual_value,created_by) VALUES($1,'2026-01-07','2026-01-14',10,$2)",[metric,staff]),/must not overlap/);
  await db.query("INSERT INTO private.impact_updates(impact_metric_id,period_start,period_end,actual_value,created_by) VALUES($1,'2026-01-08','2026-01-14',20,$2)",[metric,staff]);
  assert.equal((await row('SELECT sum(actual_value)::text AS actual FROM private.impact_updates WHERE impact_metric_id=$1',[metric])).actual,'30.00');
});
test('foreign keys protect dependent records',async () => {
  await assert.rejects(db.query('DELETE FROM private.donors WHERE id=$1',[donor]),/foreign key/);
});
test('closed grants cannot receive expenses',async () => {
  await db.query("UPDATE private.grants SET status='closed' WHERE id=$1",[grant]);
  await assert.rejects(db.query("INSERT INTO private.expenses(budget_category_id,amount,expense_date,description,created_by) VALUES($1,1,'2026-01-01','Closed',$2)",[category,staff]),/Closed grants/);
  await db.query("UPDATE private.grants SET status='active' WHERE id=$1",[grant]);
});
test('fictional seed runs with an active staff member',async () => {
  await db.exec(await readFile(new URL('../seed.sql',import.meta.url),'utf8'));
  assert.equal((await row("SELECT name FROM private.grants WHERE name='Community Meals Pilot'")).name,'Community Meals Pilot');
});
test('restricted backend role cannot provision staff or read auth users',async () => {
  await db.exec(await readFile(new URL('../backend_role.sql',import.meta.url),'utf8'));
  await db.exec('SET ROLE grant_api');
  assert.equal((await row('SELECT count(*)::int AS count FROM private.donors')).count,2);
  await assert.rejects(db.query("INSERT INTO private.staff_members(user_id,display_name) VALUES(gen_random_uuid(),'Intruder')"),/permission denied/);
  await assert.rejects(db.query('SELECT * FROM auth.users'),/permission denied/);
  await assert.rejects(db.query('DELETE FROM private.expenses'),/permission denied/);
  await db.query("INSERT INTO private.donors(name) VALUES('Allowed donor')");
  await db.exec('RESET ROLE');
});
