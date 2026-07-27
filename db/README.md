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
- `0003_enable_dashboard_rls_policies.sql` - applies (uncommented) the
  exact policies 0002 only recommended: turns on Row Level Security
  and grants the anon key full read/write on the 6 tables from 0002.
  Read the note at the top of the file before applying - it grants
  access to anyone holding the anon key, with no per-user isolation,
  because this codebase has no authentication system. This repo
  cannot confirm whether 0001, 0002, or 0003 have actually been
  applied to any live project; verify directly in the Supabase SQL
  editor (`select * from pg_tables where schemaname = 'public'` and
  `select * from pg_policies`) before relying on any of them.
