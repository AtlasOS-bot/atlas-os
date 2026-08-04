"""
Atlas web server - static asset routes.

Deliberately NOT using Vercel's public/** directory: Vercel's docs are
explicit that files placed there are served directly by the CDN,
bypassing the Python function (and therefore AuthMiddleware) entirely.
Everything here goes through an ordinary authenticated route instead -
slower than a CDN by a few milliseconds, which doesn't matter at this
traffic scale, but it means there is no unauthenticated path to any
dashboard asset.

/assets/<name> is a single wildcard-looking route but is NOT a raw
path passthrough: the resolved path is required to stay inside
dashboard/assets/ (blocks ../ traversal) and must end in .svg (the
only file type that directory currently holds).
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

router = APIRouter()

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"
ASSETS_DIR = (DASHBOARD_DIR / "assets").resolve()


@router.get("/app.js", include_in_schema=False)
async def app_js():
    return FileResponse(DASHBOARD_DIR / "app.js", media_type="application/javascript")


@router.get("/styles.css", include_in_schema=False)
async def styles_css():
    return FileResponse(DASHBOARD_DIR / "styles.css", media_type="text/css")


@router.get("/assets/{path:path}", include_in_schema=False)
async def assets(path: str):
    if not path.endswith(".svg"):
        return Response(status_code=404)

    candidate = (ASSETS_DIR / path).resolve()
    try:
        candidate.relative_to(ASSETS_DIR)
    except ValueError:
        # Resolved outside dashboard/assets/ (e.g. via ../..) - refuse
        # rather than serving whatever it pointed at.
        return Response(status_code=404)

    if not candidate.is_file():
        return Response(status_code=404)

    return FileResponse(candidate, media_type="image/svg+xml")
