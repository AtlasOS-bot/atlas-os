# Database migrations

This repository has no migration runner (no Supabase CLI project, no
Alembic, no ORM). Every Supabase table used by Atlas today, including
`opportunities` and `notifications`, was created by hand against the
live project - there is nothing here that applies SQL automatically.

Files in `db/migrations/` are plain SQL, numbered in the order they
should be applied. Apply a file by pasting it into the Supabase SQL
editor (or running it via `psql`) against the target project.

## Applied so far

- `0001_create_collector_opportunities.sql` - adds the
  `collector_opportunities` table for Atlas v21's Collector
  Intelligence Engine (Module 1). Purely additive: creates one new
  table, does not alter or drop any existing table.
- `0002_create_dashboard_user_data.sql` - adds the personal-data
  tables behind Module 8's dashboard (overrides, override history,
  notes, hearted items, hearted-item notes, opportunity images, user
  links). Purely additive. **Contains a security note you should read
  before applying** - the Row Level Security policies at the bottom
  of the file are commented-out recommendations, not applied
  automatically, and the dashboard's write features should be treated
  as unverified-secure until you've reviewed and applied appropriate
  policies for your deployment.
- `0003_enable_dashboard_rls_policies.sql` - **REVISED** for the
  password-protected deployment. The original version granted the
  anon key full read/write on the 6 tables from 0002, matching the old
  architecture where dashboard/app.js talked to Supabase directly.
  That's gone: app.js now calls this app's own `/api/*` routes
  (`server/routes_api.py`), which use the service-role key
  server-side. This file now enables RLS with **no** policies for
  anon/authenticated (deny by default) and explicitly revokes their
  table grants too. Only `service_role` (server-side only) can read or
  write these tables now.
- `0004_create_auth_tables.sql` - adds `auth_sessions` and
  `auth_login_attempts`, which `server/sessions.py` and
  `server/rate_limit.py` need for real session revocation and login
  lockout. **Apply this before deploying the FastAPI app** - login
  fails closed (same as a wrong password, by design) if these tables
  don't exist yet. RLS enabled, no anon/authenticated access, same as
  0003's revised model.
- `0005_revoke_anon_access_to_collector_opportunities.sql` - 0001
  never enabled RLS on `collector_opportunities`, so Supabase's
  default table grants have very likely left it openly readable (and
  writable) by the anon key since it was created, independent of any
  website password. This closes that gap the same way 0003 does for
  the dashboard tables. `scripts/generate_dashboard.py` was updated in
  the same change to read this table with `SUPABASE_SERVICE_KEY`
  instead of the anon key, since anon can no longer read it at all
  after this migration.

## Apply order

`0001` → `0002` → `0003` → `0004` → `0005`, all before the first
deployment of the FastAPI app. This repo cannot confirm whether any of
them have actually been applied to any live project; verify directly
in the Supabase SQL editor (`select * from pg_tables where schemaname
= 'public'`, `select * from pg_policies`, and `select grantee,
privilege_type from information_schema.role_table_grants where
table_schema = 'public'`) before relying on any of them.
