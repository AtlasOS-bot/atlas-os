"""
Atlas web server - session management.

A session is an opaque random token. The cookie holds the token plus
an HMAC signature (keyed by ATLAS_SESSION_SECRET) so a forged/tampered
cookie is rejected before any database call. The token itself is never
stored server-side - only its SHA-256 hash is, in `auth_sessions` - so
a leaked database row can't be replayed as a cookie.

Logout is real revocation, not just clearing the browser cookie:
`revoke_session` marks the row `revoked_at`, so a copied cookie stops
working immediately even if the browser never saw the logout response.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from server.supabase_client import SupabaseError

COOKIE_NAME = "atlas_session"
TABLE = "auth_sessions"
TOKEN_BYTES = 32


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


def _sign(token, session_secret):
    return hmac.new(session_secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class SessionResult:
    cookie_value: str
    expires_at: datetime


def create_session(supabase, session_secret, max_age_seconds):
    """Creates a new session row and returns the signed cookie value to
    set on the client. Raises SupabaseError if the write fails - the
    caller (auth.login) is responsible for turning that into the same
    generic failure message shown for a wrong password."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = _utc_now()
    expires_at = now + timedelta(seconds=max_age_seconds)

    supabase.insert(TABLE, {
        "session_token_hash": _hash_token(token),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "revoked_at": None,
    })

    cookie_value = f"{token}.{_sign(token, session_secret)}"
    return SessionResult(cookie_value=cookie_value, expires_at=expires_at)


def validate_session(supabase, session_secret, cookie_value):
    """Returns True if the cookie is a live, unexpired, unrevoked
    session. Never raises - a malformed cookie or a Supabase read
    failure both just mean "not authenticated," so callers don't need
    a separate error path (and the login/middleware layer never has to
    decide whether to reveal *why* a session was rejected)."""
    if not cookie_value or "." not in cookie_value:
        return False

    token, _, signature = cookie_value.partition(".")
    if not hmac.compare_digest(_sign(token, session_secret), signature):
        return False

    try:
        rows = supabase.select(TABLE, filters={"session_token_hash": _hash_token(token)}, limit=1)
    except SupabaseError:
        return False

    if not rows:
        return False

    row = rows[0]
    if row.get("revoked_at"):
        return False

    expires_at = _parse_iso(row.get("expires_at"))
    if expires_at is None or expires_at <= _utc_now():
        return False

    return True


def revoke_session(supabase, cookie_value):
    """Best-effort - logout should always clear the browser cookie even
    if this fails, so callers should not let a Supabase error here
    block the logout response."""
    if not cookie_value or "." not in cookie_value:
        return
    token, _, _ = cookie_value.partition(".")
    try:
        supabase.update(
            TABLE, {"session_token_hash": _hash_token(token)},
            {"revoked_at": _utc_now().isoformat()},
        )
    except SupabaseError:
        pass


# Bounded cleanup (expired/old-revoked sessions) lives in
# server/cleanup.py, not here - it needs to stay bounded (never an
# unbounded table scan), which server/cleanup.py handles via
# SupabaseClient.select_lt() with an explicit limit.
