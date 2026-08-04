"""
Atlas web server - FastAPI application factory.

create_app(config, supabase=None) builds the whole app. `supabase` is
injectable so tests run against FakeSupabaseClient with zero network
access and zero applied migrations - production (api/index.py) is the
only caller that leaves it as None, which wires up the real
SupabaseClient using the service key from config.

Every route is protected by AuthMiddleware except GET/POST /login -
that allowlist is the only place "this route doesn't need a session"
is decided, so a future route can't accidentally end up unprotected by
forgetting to add a per-route dependency.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from server import routes_api, routes_pages, routes_static
from server.security_headers import SecurityHeadersMiddleware
from server.sessions import COOKIE_NAME, validate_session
from server.supabase_client import SupabaseClient

PUBLIC_PATHS = {"/login", "/login.css"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        config = request.app.state.config
        supabase = request.app.state.supabase
        cookie_value = request.cookies.get(COOKIE_NAME)

        if not validate_session(supabase, config.session_secret, cookie_value):
            if request.url.path.startswith("/api/"):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return RedirectResponse("/login", status_code=303)

        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        config = request.app.state.config
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > config.max_body_bytes:
                    return JSONResponse({"error": "payload too large"}, status_code=413)
            except ValueError:
                pass
        return await call_next(request)


def create_app(config, supabase=None):
    supabase = supabase or SupabaseClient(config.supabase_url, config.supabase_service_key)

    # docs/openapi disabled - this is a private single-user app, no
    # reason to expose a machine-readable map of every route.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.state.supabase = supabase

    # Starlette runs middleware in reverse registration order (last
    # added = outermost = runs first on the way in, last on the way
    # out). BodySizeLimitMiddleware wraps AuthMiddleware so oversized
    # bodies are rejected before a session lookup runs for them.
    # SecurityHeadersMiddleware is added last (outermost of all) so it
    # sees and can decorate every response this app ever returns,
    # including the 303/401/413 responses the other two short-circuit
    # with - a redirect or error page still needs these headers.
    app.add_middleware(AuthMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(routes_pages.router)
    app.include_router(routes_static.router)
    app.include_router(routes_api.router)

    return app
