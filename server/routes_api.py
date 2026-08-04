"""
Atlas web server - protected API routes for existing Module 8 actions.

This replaces every direct-to-Supabase call dashboard/app.js used to
make with its own anon key. Same operations, same tables - just moved
server-side, behind a session + CSRF + Origin check, using the service
key that never reaches the browser. No inventory logic lives here yet;
that's explicitly future work.

Every mutating route depends on require_protected_write (Origin +
content-type + CSRF token, on top of the session check AuthMiddleware
already did for the whole request). Every request body is a Pydantic
model, so malformed input is rejected before it ever reaches Supabase.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from server.security_deps import require_protected_write
from server.supabase_client import SupabaseError

router = APIRouter(prefix="/api")

VALID_MARKET_STRENGTHS = ("STRONG", "MEDIUM", "WEAK", "UNKNOWN", None)
VALID_MARKET_TRENDS = ("RISING", "STABLE", "FALLING", "UNKNOWN", None)


def _supabase(request: Request):
    return request.app.state.supabase


def _fail(exc):
    raise HTTPException(status_code=502, detail="Could not reach the database. Try again.") from exc


@router.get("/whoami")
async def whoami():
    return {"authenticated": True}


# ---------------------------------------------------------------
# Hearted items
# ---------------------------------------------------------------

class HeartBody(BaseModel):
    opportunity_id: str


class ArchiveBody(BaseModel):
    archived: bool


class ManualItemBody(BaseModel):
    product_name: str
    image_url: str | None = None
    product_link: str | None = None
    ebay_sold_link: str | None = None
    msrp: float | None = None
    last_sold_price: float | None = None
    market_strength: str = "UNKNOWN"
    category: str | None = None
    priority: str | None = None
    target_price: float | None = None
    quantity: int | None = None
    tags: list[str] = []


class HeartedItemUpdateBody(BaseModel):
    category: str | None = None
    priority: str | None = None
    target_price: float | None = None
    quantity: int | None = None
    tags: list[str] = []
    # Identity fields - only meaningful (and only applied) for manual
    # items; sent as None/omitted when editing an Atlas-linked item.
    product_name: str | None = None
    image_url: str | None = None
    product_link: str | None = None
    ebay_sold_link: str | None = None
    msrp: float | None = None
    last_sold_price: float | None = None
    market_strength: str | None = None
    include_identity: bool = False


@router.post("/hearted", dependencies=[Depends(require_protected_write)])
async def heart(request: Request, body: HeartBody):
    try:
        return _supabase(request).insert(
            "hearted_items", {"opportunity_id": body.opportunity_id, "status": "SAVED"},
            prefer="return=minimal",
        )
    except SupabaseError as exc:
        _fail(exc)


@router.delete("/hearted/by-opportunity/{opportunity_id}", dependencies=[Depends(require_protected_write)])
async def unheart_by_opportunity(request: Request, opportunity_id: str):
    try:
        _supabase(request).delete("hearted_items", {"opportunity_id": opportunity_id})
    except SupabaseError as exc:
        _fail(exc)
    return {"ok": True}


@router.delete("/hearted/{hearted_item_id}", dependencies=[Depends(require_protected_write)])
async def unheart(request: Request, hearted_item_id: str):
    try:
        _supabase(request).delete("hearted_items", {"id": hearted_item_id})
    except SupabaseError as exc:
        _fail(exc)
    return {"ok": True}


@router.patch("/hearted/{hearted_item_id}/archive", dependencies=[Depends(require_protected_write)])
async def toggle_archive(request: Request, hearted_item_id: str, body: ArchiveBody):
    archived_at = datetime.now(timezone.utc).isoformat() if body.archived else None
    try:
        _supabase(request).update(
            "hearted_items", {"id": hearted_item_id}, {"archived_at": archived_at},
            prefer="return=minimal",
        )
    except SupabaseError as exc:
        _fail(exc)
    return {"ok": True}


@router.get("/hearted/{hearted_item_id}")
async def get_hearted_item(request: Request, hearted_item_id: str):
    try:
        rows = _supabase(request).select("hearted_items", filters={"id": hearted_item_id}, limit=1)
    except SupabaseError as exc:
        _fail(exc)
    if not rows:
        raise HTTPException(status_code=404, detail="Not found.")
    return rows[0]


@router.post("/hearted/manual", dependencies=[Depends(require_protected_write)])
async def create_manual_item(request: Request, body: ManualItemBody):
    payload = body.model_dump()
    payload["status"] = "SAVED"
    try:
        return _supabase(request).insert("hearted_items", payload, prefer="return=representation")
    except SupabaseError as exc:
        _fail(exc)


@router.patch("/hearted/{hearted_item_id}", dependencies=[Depends(require_protected_write)])
async def update_hearted_item(request: Request, hearted_item_id: str, body: HeartedItemUpdateBody):
    payload = {
        "category": body.category,
        "priority": body.priority,
        "target_price": body.target_price,
        "quantity": body.quantity,
        "tags": body.tags,
    }
    if body.include_identity:
        payload.update({
            "product_name": body.product_name,
            "image_url": body.image_url,
            "product_link": body.product_link,
            "ebay_sold_link": body.ebay_sold_link,
            "msrp": body.msrp,
            "last_sold_price": body.last_sold_price,
            "market_strength": body.market_strength or "UNKNOWN",
        })
    try:
        rows = _supabase(request).update(
            "hearted_items", {"id": hearted_item_id}, payload, prefer="return=representation",
        )
    except SupabaseError as exc:
        _fail(exc)
    if not rows:
        raise HTTPException(status_code=404, detail="Not found.")
    return rows[0]


# ---------------------------------------------------------------
# Notes
# ---------------------------------------------------------------

NOTE_TABLES = {"opportunity": "opportunity_notes", "hearted_item": "hearted_item_notes"}
NOTE_FILTER_FIELD = {"opportunity": "opportunity_id", "hearted_item": "hearted_item_id"}


class NoteBody(BaseModel):
    scope: Literal["opportunity", "hearted_item"]
    subject_id: str
    body: str


@router.get("/notes")
async def list_notes(
    request: Request,
    scope: Literal["opportunity", "hearted_item"] = Query(...),
    subject_id: str = Query(...),
):
    table = NOTE_TABLES[scope]
    field = NOTE_FILTER_FIELD[scope]
    try:
        return _supabase(request).select(table, filters={field: subject_id}, order="updated_at.desc")
    except SupabaseError as exc:
        _fail(exc)


@router.post("/notes", dependencies=[Depends(require_protected_write)])
async def add_note(request: Request, body: NoteBody):
    table = NOTE_TABLES[body.scope]
    field = NOTE_FILTER_FIELD[body.scope]
    try:
        return _supabase(request).insert(
            table, {field: body.subject_id, "body": body.body}, prefer="return=representation",
        )
    except SupabaseError as exc:
        _fail(exc)


@router.delete("/notes/{note_id}", dependencies=[Depends(require_protected_write)])
async def delete_note(request: Request, note_id: str, scope: Literal["opportunity", "hearted_item"] = Query(...)):
    table = NOTE_TABLES[scope]
    try:
        _supabase(request).delete(table, {"id": note_id})
    except SupabaseError as exc:
        _fail(exc)
    return {"ok": True}


# ---------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------

class OverrideBody(BaseModel):
    market_strength_override: str | None = None
    market_trend_override: str | None = None
    reason: str | None = None
    atlas_market_strength: str | None = None
    atlas_market_trend: str | None = None


def _record_history(supabase, opportunity_id, field_name, atlas_value, previous_value, new_value, reason):
    supabase.insert("opportunity_override_history", {
        "opportunity_id": opportunity_id,
        "field_name": field_name,
        "atlas_value_snapshot": atlas_value,
        "previous_override_value": previous_value,
        "new_override_value": new_value,
        "reason": reason,
    }, prefer="return=minimal")


@router.get("/overrides/{opportunity_id}")
async def get_override(request: Request, opportunity_id: str):
    try:
        rows = _supabase(request).select(
            "opportunity_user_overrides", filters={"opportunity_id": opportunity_id}, limit=1,
        )
    except SupabaseError as exc:
        _fail(exc)
    return rows[0] if rows else None


@router.put("/overrides/{opportunity_id}", dependencies=[Depends(require_protected_write)])
async def save_override(request: Request, opportunity_id: str, body: OverrideBody):
    if body.market_strength_override not in VALID_MARKET_STRENGTHS:
        raise HTTPException(status_code=422, detail="Invalid market strength.")
    if body.market_trend_override not in VALID_MARKET_TRENDS:
        raise HTTPException(status_code=422, detail="Invalid market trend.")

    supabase = _supabase(request)

    try:
        existing = supabase.select("opportunity_user_overrides", filters={"opportunity_id": opportunity_id}, limit=1)
        previous = existing[0] if existing else None

        payload = {
            "opportunity_id": opportunity_id,
            "market_strength_override": body.market_strength_override,
            "market_trend_override": body.market_trend_override,
            "reason": body.reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if previous:
            supabase.update(
                "opportunity_user_overrides", {"opportunity_id": opportunity_id}, payload,
                prefer="return=minimal",
            )
        else:
            supabase.insert("opportunity_user_overrides", payload, prefer="return=minimal")

        previous_strength = previous.get("market_strength_override") if previous else None
        previous_trend = previous.get("market_trend_override") if previous else None

        if body.market_strength_override != previous_strength:
            _record_history(
                supabase, opportunity_id, "market_strength", body.atlas_market_strength,
                previous_strength, body.market_strength_override, body.reason,
            )
        if body.market_trend_override != previous_trend:
            _record_history(
                supabase, opportunity_id, "market_trend", body.atlas_market_trend,
                previous_trend, body.market_trend_override, body.reason,
            )
    except SupabaseError as exc:
        _fail(exc)

    return payload


class ResetOverrideBody(BaseModel):
    atlas_market_strength: str | None = None
    atlas_market_trend: str | None = None


@router.delete("/overrides/{opportunity_id}", dependencies=[Depends(require_protected_write)])
async def reset_override(request: Request, opportunity_id: str, body: ResetOverrideBody):
    supabase = _supabase(request)
    try:
        existing = supabase.select("opportunity_user_overrides", filters={"opportunity_id": opportunity_id}, limit=1)
        if existing:
            previous = existing[0]
            supabase.delete("opportunity_user_overrides", {"opportunity_id": opportunity_id})

            if previous.get("market_strength_override"):
                _record_history(
                    supabase, opportunity_id, "market_strength", body.atlas_market_strength,
                    previous.get("market_strength_override"), None, "Reset to Atlas assessment",
                )
            if previous.get("market_trend_override"):
                _record_history(
                    supabase, opportunity_id, "market_trend", body.atlas_market_trend,
                    previous.get("market_trend_override"), None, "Reset to Atlas assessment",
                )
    except SupabaseError as exc:
        _fail(exc)

    return {"ok": True}
