"""
Atlas web server - page routes.

Serves the already-generated dashboard/*.html files (produced by
scripts/generate_dashboard.py / generate_demo_dashboard.py, unchanged)
through authenticated routes, injecting a per-session CSRF token as a
<meta> tag so app.js can read it and attach it to state-changing
requests. This module never regenerates or recomputes dashboard
content - that stays entirely in the existing Module 8 pipeline.

Demo pages return a genuine 404 when ATLAS_ENABLE_DEMO isn't set - not
a distinct "disabled" response - so their existence isn't revealed by
guessing the URL while the feature is off.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from server.auth import attempt_login, logout as revoke_current_session
from server.client_ip import resolve_client_ip
from server.csrf import csrf_token_for, is_allowed_origin, session_token_from_cookie
from server.login_page import LOGIN_CSS, render_login_page
from server.security_deps import require_protected_write
from server.sessions import COOKIE_NAME

router = APIRouter()

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


def _inject_csrf_meta(html, token):
    tag = f'  <meta name="csrf-token" content="{token}">\n'
    return html.replace("<head>\n", "<head>\n" + tag, 1)


def _serve_dashboard_file(request: Request, filename: str) -> HTMLResponse:
    path = DASHBOARD_DIR / filename
    html = path.read_text(encoding="utf-8")

    cookie_value = request.cookies.get(COOKIE_NAME)
    session_token = session_token_from_cookie(cookie_value)
    if session_token:
        token = csrf_token_for(session_token, request.app.state.config.session_secret)
        html = _inject_csrf_meta(html, token)

    return HTMLResponse(html)


@router.get("/login", include_in_schema=False)
async def login_page():
    return HTMLResponse(render_login_page(show_error=False))


@router.get("/login.css", include_in_schema=False)
async def login_css():
    # Unauthenticated by design (see PUBLIC_PATHS in app.py) - the
    # login page itself needs this before any session exists. Kept out
    # of an inline <style> block so the CSP's style-src never needs
    # 'unsafe-inline' (see server/security_headers.py).
    return Response(LOGIN_CSS, media_type="text/css")


@router.post("/login", include_in_schema=False)
async def login_submit(request: Request, password: str = Form(...)):
    config = request.app.state.config

    # TEMPORARY DEBUG - remove after diagnosing the origin check. repr()
    # deliberately used so hidden whitespace/newlines are visible in the
    # log output rather than silently invisible.
    print(
        "DEBUG /login origin check -- "
        f"Origin header: {request.headers.get('origin')!r} | "
        f"Referer header: {request.headers.get('referer')!r} | "
        f"config.public_origin: {config.public_origin!r}"
    )

    origin_ok = is_allowed_origin(request.headers.get("origin"), request.headers.get("referer"), config)

    if not origin_ok:
        return HTMLResponse(render_login_page(show_error=True), status_code=403)

    client_ip = resolve_client_ip(request, config)
    result = attempt_login(request.app.state.supabase, config, password, ip_address=client_ip)

    if not result.ok:
        return HTMLResponse(render_login_page(show_error=True), status_code=401)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME, result.cookie_value,
        max_age=result.max_age_seconds, httponly=True, secure=True, samesite="lax", path="/",
    )
    return response


@router.post("/logout", include_in_schema=False, dependencies=[Depends(require_protected_write)])
async def logout_route(request: Request):
    cookie_value = request.cookies.get(COOKIE_NAME)
    revoke_current_session(request.app.state.supabase, cookie_value)

    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/", include_in_schema=False)
async def home(request: Request):
    return _serve_dashboard_file(request, "index.html")


@router.get("/index.html", include_in_schema=False)
async def index_html(request: Request):
    return _serve_dashboard_file(request, "index.html")


@router.get("/hearted.html", include_in_schema=False)
async def hearted_html(request: Request):
    return _serve_dashboard_file(request, "hearted.html")


@router.get("/demo-index.html", include_in_schema=False)
async def demo_index_html(request: Request):
    if not request.app.state.config.enable_demo:
        return HTMLResponse("Not Found", status_code=404)
    return _serve_dashboard_file(request, "demo-index.html")


@router.get("/demo-hearted.html", include_in_schema=False)
async def demo_hearted_html(request: Request):
    if not request.app.state.config.enable_demo:
        return HTMLResponse("Not Found", status_code=404)
    return _serve_dashboard_file(request, "demo-hearted.html")
