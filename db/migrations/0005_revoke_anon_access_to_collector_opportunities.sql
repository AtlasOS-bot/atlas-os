-- Atlas v21: password-protected deployment foundation
--
-- db/migrations/0001_create_collector_opportunities.sql created this
-- table with no RLS statement at all. Supabase's default behavior for
-- a table created this way grants broad read/write privileges to the
-- anon and authenticated roles at the schema level, independent of
-- RLS - meaning collector_opportunities has very likely been openly
-- readable (and writable) by anyone holding the anon key since the
-- day it was created, regardless of any website password.
--
-- The anon key is not a secret (see db/README.md and dashboard/app.js's
-- git history) - it was always meant to be public. Once the website
-- password is the only access control, that assumption is no longer
-- acceptable: querying Supabase directly with the anon key must not
-- be able to bypass it. This migration closes that gap for
-- collector_opportunities specifically (0003 already closed it for
-- the 6 dashboard tables; 0004's new auth tables are locked down from
-- the start).
--
-- scripts/generate_dashboard.py was updated in the same change to
-- read this table with SUPABASE_SERVICE_KEY instead of the anon key,
-- since after this migration the anon key can no longer read it at
-- all.
--
-- This repository has no migration tooling - apply this file manually
-- via the Supabase SQL editor (or `psql`) against the target project,
-- after 0001-0004.

alter table public.collector_opportunities enable row level security;

revoke all on public.collector_opportunities from anon, authenticated;
