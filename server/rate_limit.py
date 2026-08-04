"""
Atlas web server - login rate limiting / lockout.

Backed by a small Supabase table (auth_login_attempts) rather than an
in-process counter, because Vercel Functions don't guarantee a warm,
shared process between requests - an in-memory counter would silently
reset on a cold start and stop protecting anything.

Two independent rolling-window checks, either of which can trigger a
lockout:

- Per-IP: too many failures from the SAME client IP locks out just
  that IP. Requires a trusted IP (see server/client_ip.py) - an
  unknown IP can't be checked per-IP and falls back to the global
  check alone.
- Global: too many failures system-wide, regardless of IP, locks out
  everyone. This is the backstop against an attacker rotating across
  many IP addresses specifically to stay under the per-IP threshold -
  deliberately a much higher ("conservative") ceiling than the per-IP
  one, since it also has to tolerate ordinary traffic.

Both checks are the same code path whether Supabase is briefly
unreachable or the password was wrong - see auth.py for why the two
are never distinguished to the caller.
"""

from datetime import datetime, timedelta, timezone

TABLE = "auth_login_attempts"


def _utc_now():
    return datetime.now(timezone.utc)


def _parse_iso(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def record_attempt(supabase, success, ip_address=None):
    supabase.insert(TABLE, {
        "attempted_at": _utc_now().isoformat(),
        "success": bool(success),
        "ip_address": ip_address,
    }, prefer="return=minimal")


def _count_recent_failures(supabase, window_seconds, extra_filters=None):
    cutoff = _utc_now() - timedelta(seconds=window_seconds)
    filters = {"success": False, **(extra_filters or {})}
    rows = supabase.select(TABLE, filters=filters)
    return sum(
        1 for row in rows
        if (attempted := _parse_iso(row.get("attempted_at"))) is not None and attempted >= cutoff
    )


def is_locked_out_for_ip(supabase, ip_address, threshold, window_seconds):
    """False (never locked out via this check) when ip_address is None -
    an untrusted/unknown IP can't be attributed a per-IP history, so
    the global check is the only thing that can lock it out."""
    if ip_address is None:
        return False
    return _count_recent_failures(supabase, window_seconds, {"ip_address": ip_address}) >= threshold


def is_globally_locked_out(supabase, threshold, window_seconds):
    return _count_recent_failures(supabase, window_seconds) >= threshold


def is_locked_out(supabase, config, ip_address):
    """Combines both checks - locked out if either fires."""
    if is_globally_locked_out(supabase, config.global_lockout_threshold, config.lockout_window_seconds):
        return True
    return is_locked_out_for_ip(supabase, ip_address, config.lockout_threshold, config.lockout_window_seconds)


# Bounded cleanup of old attempt records lives in server/cleanup.py,
# not here - see that module for why (never an unbounded table scan).
