-- Atlas v21: Collector Intelligence Engine - Module 8 (integration layer)
--
-- REVISED. The original version of this file granted the anon role
-- full read/write access to these tables, matching the old
-- architecture where dashboard/app.js talked to Supabase directly
-- with the anon key. That architecture is gone: app.js now calls this
-- app's own /api/* routes (server/routes_api.py), which use the
-- service-role key server-side and sit behind a password-protected
-- session. The anon key no longer needs - and must not have - any
-- access to these tables at all, or the website password could be
-- bypassed entirely by querying Supabase directly with the anon key,
-- which is not a secret (it is already public, embedded in the pre-
-- rewire dashboard/index.html served to anyone).
--
-- This file enables Row Level Security on all 7 dashboard tables and
-- adds NO policies for anon (or authenticated) - RLS with zero
-- policies means "deny by default" for every role except
-- service_role, which bypasses RLS entirely by design and is the only
-- credential server/ code ever uses.
--
-- This repository has no migration tooling - apply this file manually
-- via the Supabase SQL editor (or `psql`) against the target project,
-- same as 0001, 0002, 0004, and 0005. Nothing in this repository
-- executes it automatically, and nothing in this repository has
-- verified whether it has been applied.

alter table public.opportunity_user_overrides enable row level security;
alter table public.opportunity_override_history enable row level security;
alter table public.opportunity_notes enable row level security;
alter table public.hearted_items enable row level security;
alter table public.hearted_item_notes enable row level security;
alter table public.opportunity_images enable row level security;
alter table public.user_external_links enable row level security;

-- Belt-and-suspenders: Supabase grants broad table privileges to the
-- anon/authenticated roles by default at table-creation time,
-- independent of RLS. Revoking them explicitly means even a table
-- where RLS was accidentally left off (e.g. a future table someone
-- forgets to enable RLS on) doesn't fall back to being anon-writable
-- by default - the grant itself is gone, not just gated by a policy.
revoke all on public.opportunity_user_overrides from anon, authenticated;
revoke all on public.opportunity_override_history from anon, authenticated;
revoke all on public.opportunity_notes from anon, authenticated;
revoke all on public.hearted_items from anon, authenticated;
revoke all on public.hearted_item_notes from anon, authenticated;
revoke all on public.opportunity_images from anon, authenticated;
revoke all on public.user_external_links from anon, authenticated;
