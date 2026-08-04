"""
Atlas web server - security response headers.

Applied to EVERY response (HTML, static assets, API JSON, redirects,
error responses) by SecurityHeadersMiddleware - see server/app.py's
comment on middleware ordering for why this one has to be the
outermost layer to actually see every response, including ones an
inner middleware (AuthMiddleware, BodySizeLimitMiddleware) short-
circuits before a route handler ever runs.

CSP notes:
- No 'unsafe-eval' anywhere.
- No 'unsafe-inline' anywhere either. The one place that would have
  needed it (the login page's CSS) was moved to an external file
  instead (server/login_page.py, served via /login.css) - see that
  module's docstring. There is no other inline <style>/<script> or
  style="..."/on*="..." attribute anywhere in this app (dashboard/app.js
  and collector_intelligence/dashboard_render.py were both checked).
- img-src allows any https: source, not a fixed allowlist - Atlas
  pulls product images from whatever retailer/source a given
  opportunity or manually-added item names (collector_intelligence/
  dashboard_view.py's resolve_image, and inventory items later), which
  isn't a fixed set of hosts. Same-origin (this app's own SVG assets)
  and https: cover every legitimate case; http: and data:/blob: are
  deliberately excluded.
- connect-src 'self' is sufficient because dashboard/app.js only ever
  calls same-origin /api/* routes now (no more direct Supabase calls
  from the browser).
"""

from starlette.middleware.base import BaseHTTPMiddleware

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' https:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    # Legacy fallback alongside CSP's frame-ancestors - harmless
    # belt-and-suspenders for anything not honoring the CSP directive.
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), "
        "usb=(), interest-cohort=()"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response
