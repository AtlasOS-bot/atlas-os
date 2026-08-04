"""
Atlas web server - bounded cleanup of auth_sessions / auth_login_attempts.

Every delete here is bounded: each call selects at most `batch_size`
candidate rows (via SupabaseClient.select_lt's `limit`) and deletes
exactly those, one at a time. A single call can never issue an
unbounded database operation, no matter how large the backlog is -
that's the point of doing this at all, since one of these runs
opportunistically on the login path where an unbounded scan would be
an easy way to make every hundredth login slow (or, on a much larger
backlog than expected, very slow).

Two entry points:
- maybe_opportunistic_cleanup(supabase, config) - called from the
  login path (server/auth.py). Small random chance, one bounded batch
  per category, and any failure is swallowed - cleanup must never be
  the reason a login fails.
- run_full_cleanup(supabase, config) - for the future morning
  workflow. Repeats bounded batches per category until each is clear
  or a safety cap of iterations is hit, so a real backlog actually
  gets cleared over a run without ever making a single unbounded call.
"""

import random
from datetime import datetime, timedelta, timezone

from server.supabase_client import SupabaseError

SESSIONS_TABLE = "auth_sessions"
ATTEMPTS_TABLE = "auth_login_attempts"


def _utc_now():
    return datetime.now(timezone.utc)


def _delete_bounded_batch(supabase, table, field, cutoff_iso, batch_size):
    candidates = supabase.select_lt(table, field, cutoff_iso, limit=batch_size)
    for row in candidates:
        supabase.delete(table, {"id": row["id"]})
    return len(candidates)


def _run_cleanup_once(supabase, config):
    now_iso = _utc_now().isoformat()
    revoked_cutoff = (_utc_now() - timedelta(days=config.session_revoked_retention_days)).isoformat()
    attempts_cutoff = (_utc_now() - timedelta(days=config.login_attempt_retention_days)).isoformat()
    batch_size = config.cleanup_batch_size

    return {
        "expired_sessions": _delete_bounded_batch(supabase, SESSIONS_TABLE, "expires_at", now_iso, batch_size),
        "revoked_sessions": _delete_bounded_batch(supabase, SESSIONS_TABLE, "revoked_at", revoked_cutoff, batch_size),
        "login_attempts": _delete_bounded_batch(supabase, ATTEMPTS_TABLE, "attempted_at", attempts_cutoff, batch_size),
    }


def maybe_opportunistic_cleanup(supabase, config, random_fn=random.random):
    """Best-effort, low-frequency, single bounded batch per category.
    Never raises - a cleanup failure must never turn into a login
    failure. Returns None when it didn't run (the common case) or a
    dict of counts when it did."""
    if random_fn() >= config.cleanup_probability:
        return None
    try:
        return _run_cleanup_once(supabase, config)
    except SupabaseError:
        return None


def run_full_cleanup(supabase, config, max_iterations=50):
    """For the future morning workflow to call directly. Still bounded
    per call (max_iterations * cleanup_batch_size rows total, an
    explicit safety cap) - not truly unlimited, just large enough to
    clear a realistic backlog in one run. Stops early once a full pass
    finds nothing left in any category."""
    totals = {"expired_sessions": 0, "revoked_sessions": 0, "login_attempts": 0}
    for _ in range(max_iterations):
        result = _run_cleanup_once(supabase, config)
        for key, count in result.items():
            totals[key] += count
        if sum(result.values()) == 0:
            break
    return totals
