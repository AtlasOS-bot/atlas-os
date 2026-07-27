-- Atlas v21: Collector Intelligence Engine - Module 8 (integration layer)
--
-- Applies the RLS policies that db/migrations/0002_create_dashboard_user_data.sql
-- listed as a commented-out RECOMMENDATION. This file changes nothing
-- about their wording or scope - it only removes the comment markers
-- so they can actually be applied. Scoped to the 6 Module 8 tables
-- only; does not touch collector_opportunities or any legacy table.
--
-- This repository has no migration tooling - apply this file manually
-- via the Supabase SQL editor (or `psql`) against the target project,
-- same as 0001 and 0002. Nothing in this repository executes it
-- automatically, and nothing in this repository has verified whether
-- it has been applied.
--
-- WHAT "SAFE" MEANS HERE, AND WHAT IT DOES NOT MEAN
-- ====================================================
-- These policies grant the `anon` role (the same publishable key
-- already hardcoded in dashboard/app.js and the legacy dashboard)
-- unrestricted read/write on these 6 tables. That is "safe" only in
-- the narrow sense that:
--   - it is no more permissive than a table with RLS never enabled
--     at all (Supabase's default for a freshly created table is NO
--     row-level restriction whatsoever until you turn RLS on) - so
--     applying this is a strict improvement over doing nothing, and
--   - it never grants the anon key any access to service-role-only
--     operations or other tables.
-- It does NOT provide per-user isolation: this codebase has no
-- Supabase Auth / users table anywhere, so there is no authenticated
-- identity to scope a policy to. Anyone holding this anon key can
-- read and write every row in these 6 tables. That is the accepted
-- model for a single personal user running this tool locally - it is
-- not appropriate for a multi-user or public deployment without
-- adding real authentication and rewriting these policies to scope
-- by user id.

alter table public.opportunity_user_overrides enable row level security;
create policy "anon full access" on public.opportunity_user_overrides
    for all using (true) with check (true);

alter table public.opportunity_override_history enable row level security;
create policy "anon full access" on public.opportunity_override_history
    for all using (true) with check (true);

alter table public.opportunity_notes enable row level security;
create policy "anon full access" on public.opportunity_notes
    for all using (true) with check (true);

alter table public.hearted_items enable row level security;
create policy "anon full access" on public.hearted_items
    for all using (true) with check (true);

alter table public.hearted_item_notes enable row level security;
create policy "anon full access" on public.hearted_item_notes
    for all using (true) with check (true);

alter table public.opportunity_images enable row level security;
create policy "anon full access" on public.opportunity_images
    for all using (true) with check (true);

alter table public.user_external_links enable row level security;
create policy "anon full access" on public.user_external_links
    for all using (true) with check (true);
