-- Atlas v21: password-protected deployment foundation
--
-- Creates the two tables server/ needs for real session revocation and
-- login rate limiting (see server/sessions.py, server/rate_limit.py).
-- Purely additive - does not alter any existing table.
--
-- This repository has no migration tooling - apply this file manually
-- via the Supabase SQL editor (or `psql`) against the target project.
-- Nothing in this repository executes it automatically. Apply this
-- AFTER 0001-0003 and BEFORE deploying the FastAPI app: login itself
-- depends on auth_sessions and auth_login_attempts existing - without
-- them, every login attempt fails closed (see server/auth.py, which
-- treats any Supabase error the same as a wrong password).
--
-- Both tables are for server-side use only. The anon key gets no
-- access at all - only service_role (which bypasses RLS by design)
-- ever reads or writes them, matching db/migrations/0003's revised
-- "deny anon everywhere" model.

create table if not exists public.auth_sessions (
    id uuid primary key default gen_random_uuid(),
    -- SHA-256 hex of the session token. The raw token is never stored -
    -- only ever exists in the signed cookie the browser holds - so a
    -- leaked row can't be replayed as a valid cookie.
    session_token_hash text not null unique,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    -- Logout sets this rather than deleting the row, so the same
    -- session_token_hash can't be silently reused by a duplicate
    -- insert - not that anything in this codebase would do that, but
    -- it's cheap to make an already-used hash permanently invalid.
    revoked_at timestamptz
);

-- No separate index on session_token_hash: the `unique` constraint
-- above already creates one automatically. A second, single-column
-- index on the same column would be pure duplication - extra write
-- overhead on every insert/update with no query benefit.
create index if not exists auth_sessions_expires_at_idx
    on public.auth_sessions (expires_at);


create table if not exists public.auth_login_attempts (
    id uuid primary key default gen_random_uuid(),
    attempted_at timestamptz not null default now(),
    success boolean not null,
    -- Best-effort, not load-bearing for the lockout decision itself
    -- (see server/rate_limit.py - lockout is a global rolling-window
    -- count, not per-IP, since this is a single-owner app). Kept for
    -- your own later review of who's been trying.
    ip_address text
);

create index if not exists auth_login_attempts_attempted_at_idx
    on public.auth_login_attempts (attempted_at);


alter table public.auth_sessions enable row level security;
alter table public.auth_login_attempts enable row level security;

revoke all on public.auth_sessions from anon, authenticated;
revoke all on public.auth_login_attempts from anon, authenticated;
