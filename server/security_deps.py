"""
Atlas web server - FastAPI-specific request guards for state-changing
API routes. The framework-agnostic checks themselves live in csrf.py;
this module is just the glue that reads them off a Starlette Request.

Applied only to POST/PATCH/DELETE routes under /api/* - GET requests
there are already gated by AuthMiddleware and don't mutate anything,
so they don't need Origin/CSRF/content-type checks.
"""

from fastapi import HTTPException, Request

from server.csrf import CSRF_HEADER, is_allowed_origin, validate_csrf_header
from server.sessions import COOKIE_NAME

_REJECTED = "Request rejected."  # deliberately generic - see login_page.py for why


async def require_protected_write(request: Request):
    config = request.app.state.config
    cookie_value = request.cookies.get(COOKIE_NAME)

    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail=_REJECTED)

    if not is_allowed_origin(request.headers.get("origin"), request.headers.get("referer"), config):
        raise HTTPException(status_code=403, detail=_REJECTED)

    if not validate_csrf_header(request.headers.get(CSRF_HEADER), cookie_value, config.session_secret):
        raise HTTPException(status_code=403, detail=_REJECTED)
