"""
Atlas web server - login orchestration.

Ties password verification, rate limiting, and session creation
together behind one function that always returns the same shape of
result on any failure - wrong password, active lockout, or Supabase
being briefly unreachable all collapse to the same LoginResult(ok=False).
This is deliberate: the login screen must never let a visitor tell
those cases apart (see the security requirements this implements).
"""

from dataclasses import dataclass

from server.cleanup import maybe_opportunistic_cleanup
from server.passwords import verify_password
from server.rate_limit import is_locked_out, record_attempt
from server.sessions import create_session, revoke_session
from server.supabase_client import SupabaseError


@dataclass
class LoginResult:
    ok: bool
    cookie_value: str | None = None
    max_age_seconds: int | None = None


def attempt_login(supabase, config, password, ip_address=None):
    try:
        if is_locked_out(supabase, config, ip_address):
            record_attempt(supabase, success=False, ip_address=ip_address)
            return LoginResult(ok=False)

        password_ok = verify_password(password, config.password_hash)
        record_attempt(supabase, success=password_ok, ip_address=ip_address)

        if not password_ok:
            return LoginResult(ok=False)

        session = create_session(supabase, config.session_secret, config.session_max_age_seconds)
        result = LoginResult(
            ok=True, cookie_value=session.cookie_value,
            max_age_seconds=config.session_max_age_seconds,
        )
    except SupabaseError:
        # Same outward result as a wrong password or an active
        # lockout - never a distinguishable error for the caller.
        return LoginResult(ok=False)

    # Opportunistic housekeeping, after the real login decision is
    # already made - never allowed to affect the result above.
    maybe_opportunistic_cleanup(supabase, config)
    return result


def logout(supabase, cookie_value):
    revoke_session(supabase, cookie_value)
