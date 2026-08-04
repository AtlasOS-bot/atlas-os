"""
Atlas web server - trusted client IP resolution.

Generic X-Forwarded-For handling is not safe to trust - any client can
set it to claim to be someone else's IP. Vercel is a documented
exception: Vercel's own docs
(https://vercel.com/docs/headers/request-headers) state plainly that
Vercel overwrites X-Forwarded-For at its edge and does NOT forward any
client-supplied value through ("This restriction is in place to
prevent IP spoofing"). x-vercel-forwarded-for carries the same value
but is documented to survive an additional proxy a user might place in
front of Vercel, where a plain x-forwarded-for could be overwritten by
that proxy instead - so it's checked first.

This is trusted ONLY when config says the request is actually arriving
via Vercel (config.trust_vercel_ip_headers, true in production). It is
never read in development, and Host/X-Forwarded-Host are never read
here at all (Vercel documents both as reflecting whatever the client
addressed the request to, not something Vercel independently verifies -
see server/csrf.py's origin handling for the same reasoning).
"""

TRUSTED_VERCEL_IP_HEADERS = ("x-vercel-forwarded-for", "x-forwarded-for")


def resolve_client_ip(request, config):
    """Returns a best-effort client IP string, or None when it can't
    be trusted - callers (server/rate_limit.py) must treat None as
    "no per-IP identity available" and fall back to the global lockout
    check alone, never as "trust some other value instead."""
    if config.trust_vercel_ip_headers:
        for header_name in TRUSTED_VERCEL_IP_HEADERS:
            value = request.headers.get(header_name)
            if value:
                # Vercel's own value is a single IP, not a chain, but
                # take only the first entry defensively either way -
                # never trust anything after the first hop as "closer
                # to the client."
                candidate = value.split(",")[0].strip()
                if candidate:
                    return candidate
        # Production but neither trusted header is present - falling
        # back to request.client.host here would just be Vercel's own
        # proxy IP (the same value for every visitor), not the real
        # client. Treat it as unknown rather than pretend that's a
        # meaningful per-IP identity.
        return None

    return request.client.host if request.client else None
