"""
Atlas web server - CSRF and request-origin protection.

SameSite=Lax cookies alone are not treated as sufficient (some
navigations and older browsers still send them cross-site). Every
state-changing API request is checked twice, independently:

1. Origin (or Referer, if Origin is absent) must match the site's own
   origin - cheap, and blocks the vast majority of cross-site attempts
   before any token comparison happens.
2. A per-session CSRF token, derived from the session token via HMAC
   with a domain-separated label (so it can never collide with the
   session cookie's own signature), must be present as a header. A
   cross-origin attacker page can trigger a request but - same-origin
   policy - can never read this page's DOM to obtain the token, so it
   can't reproduce this header even blindly.

Pure functions here take plain strings, not framework Request objects,
so they're testable without spinning up FastAPI.
"""

import hashlib
import hmac
from urllib.parse import urlparse

CSRF_HEADER = "X-CSRF-Token"
_CSRF_LABEL = "csrf"


def csrf_token_for(session_token, session_secret):
    message = f"{_CSRF_LABEL}:{session_token}".encode("utf-8")
    return hmac.new(session_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def session_token_from_cookie(cookie_value):
    if not cookie_value or "." not in cookie_value:
        return None
    token, _, _ = cookie_value.partition(".")
    return token


def validate_csrf_header(header_value, cookie_value, session_secret):
    session_token = session_token_from_cookie(cookie_value)
    if not session_token or not header_value:
        return False
    expected = csrf_token_for(session_token, session_secret)
    return hmac.compare_digest(expected, header_value)


def _origin_of(url):
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def validate_origin(origin_header, referer_header, expected_origin):
    """Prefers the Origin header; falls back to Referer's origin if
    Origin is absent (some same-site requests omit Origin but still
    send Referer). Rejects if neither is present - a same-origin
    fetch/XHR from this app's own pages always sends at least one.
    Exact string equality only - no prefix/suffix/substring matching,
    so a lookalike host (a subdomain, a suffix trick, a different
    port) is never accepted."""
    candidate = _origin_of(origin_header) or _origin_of(referer_header)
    if not candidate or not expected_origin:
        return False
    return candidate == expected_origin


_LOCALHOST_HOSTS = ("localhost", "127.0.0.1")


def is_valid_origin_string(value, allow_http_localhost=False):
    """Strict format check for a would-be origin value (e.g. the
    ATLAS_PUBLIC_ORIGIN environment variable): must be exactly
    `scheme://host` or `scheme://host:port` and nothing else - no
    path, no query, no fragment, no userinfo (`user@host`), no
    wildcard character, no whitespace, no trailing slash. HTTPS only,
    except http://localhost or http://127.0.0.1 (any/no port) when
    `allow_http_localhost` is explicitly passed - callers only do that
    in development/test mode (see server/config.py), never in
    production."""
    if not value or any(ch.isspace() for ch in value) or "@" in value or "*" in value:
        return False

    parsed = urlparse(value)
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        return False
    if not parsed.hostname:
        return False

    reconstructed = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        reconstructed += f":{parsed.port}"
    if reconstructed != value:
        return False

    if parsed.scheme == "https":
        return True
    return bool(allow_http_localhost and parsed.scheme == "http" and parsed.hostname in _LOCALHOST_HOSTS)


def _is_localhost_origin(candidate):
    """Fixed-pattern check, never derived from any per-request header -
    the only thing development mode is allowed to accept when
    ATLAS_PUBLIC_ORIGIN isn't configured."""
    parsed = urlparse(candidate)
    reconstructed = f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")
    return reconstructed == candidate and parsed.scheme == "http" and parsed.hostname in _LOCALHOST_HOSTS


def is_allowed_origin(origin_header, referer_header, config):
    """The entry point routes actually use. Never derives the expected
    origin from the request's own Host/URL - only from
    config.public_origin (required and format-validated at config-load
    time in production) or, in development mode with no public_origin
    configured, a fixed localhost-only pattern. Production with no
    public_origin configured fails closed (returns False) rather than
    falling back to anything request-derived - this should be
    unreachable in practice since load_config_from_env refuses to
    start that way, but this function doesn't rely on that."""
    candidate = _origin_of(origin_header) or _origin_of(referer_header)
    if not candidate:
        return False

    if config.public_origin:
        return candidate == config.public_origin

    if config.environment == "development":
        return _is_localhost_origin(candidate)

    return False
