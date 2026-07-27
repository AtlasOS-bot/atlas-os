"""
Atlas v21 - Module 8: dashboard view-model layer.

Pure, deterministic, fully-tested Python. Every classification the
dashboard shows (market strength, confidence, demand tags, unit
scope, relative timestamps, resolved image, effective override
values) is computed HERE, not in the browser - the frontend only
renders whatever these functions produce.

Nothing here scores an opportunity or picks a recommendation - it
reuses Module 3's ALREADY-COMPUTED evidence-based scores
(demand_score, scarcity_score, risk_score, confidence_score) to
derive a simpler presentation bucket, and reuses Module 3's existing
complete-set helpers rather than re-deriving unit-scope logic. It
never touches `recommendation`/`primary_strategy`.

Overrides are applied here at READ time only - nothing in this module
ever mutates a CollectorOpportunity, its evidence, or its raw source
fields. Notes are surfaced only as a presence flag/count, never as
text fed back into anything upstream.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from collector_intelligence.dashboard_models import VALID_LINK_TYPES
from collector_intelligence.scoring import (
    is_complete_set_mismatch,
    product_represents_complete_set,
    resale_refers_to_complete_set,
)
from collector_intelligence.summary import format_money


PLACEHOLDER_IMAGE_URL = "assets/placeholder.svg"
PLACEHOLDER_ALT_TEXT = "No product image available"

MAX_DEMAND_TAGS = 3


def _utc_now():
    return datetime.now(timezone.utc)


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ---------------------------------------------------------------
# Classification (reuses Module 3's already-computed scores)
# ---------------------------------------------------------------

def classify_market_strength(opportunity, evaluation):
    """
    STRONG / MEDIUM / WEAK / UNKNOWN - a presentation bucket over
    Module 3's existing demand_score/scarcity_score/risk_score, not a
    new scoring algorithm. Never derived from recommendation or
    primary_strategy.
    """
    has_price_evidence = any([
        opportunity.recent_sold_price is not None,
        opportunity.current_market_price is not None,
        opportunity.estimated_market_price is not None,
    ])
    has_scored_evidence = evaluation.demand_score > 0 or evaluation.scarcity_score > 0

    if not has_price_evidence and not has_scored_evidence:
        return "UNKNOWN"

    blended = (
        0.4 * evaluation.demand_score
        + 0.3 * evaluation.scarcity_score
        + 0.3 * (100 - evaluation.risk_score)
    )

    if blended >= 65:
        return "STRONG"
    if blended >= 35:
        return "MEDIUM"
    return "WEAK"


def classify_confidence(evaluation):
    """HIGH / MEDIUM / LOW - a direct, separate bucket of
    confidence_score. Never blended into market_strength."""
    if evaluation.confidence_score >= 70:
        return "HIGH"
    if evaluation.confidence_score >= 40:
        return "MEDIUM"
    return "LOW"


_TREND_FROM_DEMAND_DIRECTION = {
    "SURGING": "RISING",
    "RISING": "RISING",
    "FLAT": "STABLE",
    "FALLING": "FALLING",
}


def classify_market_trend(opportunity):
    return _TREND_FROM_DEMAND_DIRECTION.get(opportunity.demand_direction, "UNKNOWN")


def resolve_unit_scope_label(opportunity):
    """Reuses Module 3's existing complete-set helpers - no new
    unit-scope derivation logic."""
    if product_represents_complete_set(opportunity) or resale_refers_to_complete_set(opportunity):
        return "Complete set"
    return "Single item"


# ---------------------------------------------------------------
# Demand tags - short tags only, capped at MAX_DEMAND_TAGS, ordered
# so the most decision-relevant caveats surface first.
# ---------------------------------------------------------------

def _has_complete_set_caveat(opportunity):
    return resale_refers_to_complete_set(opportunity) and not product_represents_complete_set(opportunity)


def _has_thin_sales_data(opportunity):
    return opportunity.sold_listing_count is not None and opportunity.sold_listing_count < 3


def _has_high_asking_spread(opportunity):
    if opportunity.current_market_price is None or opportunity.recent_sold_price is None:
        return False
    if opportunity.recent_sold_price <= 0:
        return False
    return (opportunity.current_market_price / opportunity.recent_sold_price) >= 1.3


_DEMAND_TAG_RULES = [
    (_has_complete_set_caveat, "Complete set"),
    (_has_thin_sales_data, "Few confirmed sales"),
    (lambda o: (o.status or "").strip().lower() == "restocked", "Restock risk"),
    (lambda o: o.event_exclusive or o.convention_exclusive, "Event exclusive"),
    (lambda o: o.tournament_exclusive, "Player demand"),
    (lambda o: o.exclusive_promo, "Limited promo"),
    (lambda o: o.limited_quantity or (o.stated_quantity is not None and o.stated_quantity <= 500), "Low supply"),
    (lambda o: o.source_type == "OFFICIAL" and o.retailer_exclusive, "Official exclusive"),
    (lambda o: bool(o.sealed_product), "Sealed demand"),
    (lambda o: bool(o.artist_name), "Artist demand"),
    (lambda o: bool(o.character_names), "Popular character"),
    (lambda o: bool(o.sellout_speed), "Fast sell-through"),
    (_has_high_asking_spread, "High asking prices"),
]


def select_demand_tags(opportunity, evaluation, override_tags=None):
    """Returns at most MAX_DEMAND_TAGS short tags. If a user override
    list is supplied, it wins outright (still capped)."""
    if override_tags is not None:
        return list(override_tags)[:MAX_DEMAND_TAGS]

    tags = []
    for predicate, tag in _DEMAND_TAG_RULES:
        if predicate(opportunity):
            tags.append(tag)
        if len(tags) >= MAX_DEMAND_TAGS:
            break

    if len(tags) < MAX_DEMAND_TAGS and evaluation.hype_score >= 60 and "Hype-driven" not in tags:
        tags.append("Hype-driven")

    if not tags and evaluation.collector_score >= 50:
        tags.append("Collector demand")

    return tags[:MAX_DEMAND_TAGS]


# ---------------------------------------------------------------
# Relative time formatting
# ---------------------------------------------------------------

def format_relative_time(timestamp, now=None):
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return "Unknown"

    now = now or _utc_now()
    seconds = max(0, (now - parsed).total_seconds())

    if seconds < 60:
        return "Updated just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"Updated {minutes}m ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"Updated {hours}h ago"
    days = int(seconds // 86400)
    if days < 30:
        return f"Updated {days}d ago"
    months = int(days // 30)
    if months < 12:
        return f"Updated {months}mo ago"
    years = int(days // 365)
    return f"Updated {years}y ago"


# ---------------------------------------------------------------
# Image resolution
# ---------------------------------------------------------------

@dataclass
class ImageViewModel:
    url: str
    alt_text: str
    source_label: str | None
    is_placeholder: bool

    def to_dict(self):
        return asdict(self)


def resolve_image(opportunity, override=None, image_record=None):
    """Priority: user override > OpportunityImage record (Atlas-
    sourced: official/retailer/secondary, per whatever image_record
    itself represents) > placeholder. Never fetches or scrapes."""
    if override and override.image_override_url:
        return ImageViewModel(
            url=override.image_override_url,
            alt_text=opportunity.product_name or "Product image",
            source_label="User override",
            is_placeholder=False,
        )

    if image_record and image_record.primary_image_url:
        return ImageViewModel(
            url=image_record.primary_image_url,
            alt_text=image_record.image_alt_text or opportunity.product_name or "Product image",
            source_label=image_record.image_source_name,
            is_placeholder=False,
        )

    return ImageViewModel(
        url=PLACEHOLDER_IMAGE_URL,
        alt_text=PLACEHOLDER_ALT_TEXT,
        source_label=None,
        is_placeholder=True,
    )


# ---------------------------------------------------------------
# Effective-value resolution (override application, non-mutating)
# ---------------------------------------------------------------

def effective_value(atlas_value, override_value):
    """Generic 'override wins if present, else Atlas value' rule.
    Computed every call - never persisted."""
    return override_value if override_value is not None else atlas_value


# ---------------------------------------------------------------
# Links
# ---------------------------------------------------------------

@dataclass
class LinkViewModel:
    label: str
    url: str | None
    available: bool

    def to_dict(self):
        return asdict(self)


_LINK_LABELS = {
    "product": "View Product",
    "official_source": "Official Source",
    "ebay_sold": "eBay Sold",
    "current_listings": "Current Listings",
    "evidence": "Evidence",
}


def resolve_links(opportunity, user_links=None):
    """
    Returns {link_type: LinkViewModel}. `user_links` is a list of
    UserExternalLink rows scoped to this opportunity - they always win
    over Atlas-derived defaults. eBay Sold and Current Listings never
    get an Atlas-derived default value: an asking-listings search URL
    must never be silently presented as a sold-listings link.
    """
    user_by_type = {link.link_type: link for link in (user_links or [])}

    resolved = {}
    for link_type in VALID_LINK_TYPES:
        label = _LINK_LABELS[link_type]

        if link_type in user_by_type:
            resolved[link_type] = LinkViewModel(label=label, url=user_by_type[link_type].url, available=True)
            continue

        url = None
        if link_type == "product":
            url = opportunity.purchase_url
        elif link_type == "official_source" and opportunity.source_type == "OFFICIAL":
            url = opportunity.source_url

        resolved[link_type] = LinkViewModel(label=label, url=url, available=url is not None)

    return resolved


# ---------------------------------------------------------------
# Card + details view models
# ---------------------------------------------------------------

@dataclass
class ProductCardViewModel:
    opportunity_id: str
    product_name: str
    image: ImageViewModel
    updated_relative: str
    market_strength: str
    market_strength_is_override: bool
    atlas_market_strength: str
    confidence: str
    msrp_display: str
    last_sold_display: str
    unit_scope: str
    unit_scope_is_caution: bool
    market_trend: str
    atlas_market_trend: str
    demand_tags: list[str]
    links: dict[str, LinkViewModel]
    hearted: bool
    hearted_at: str | None
    has_notes: bool
    has_override: bool

    def to_dict(self):
        return {
            "opportunity_id": self.opportunity_id,
            "product_name": self.product_name,
            "image": self.image.to_dict(),
            "updated_relative": self.updated_relative,
            "market_strength": self.market_strength,
            "market_strength_is_override": self.market_strength_is_override,
            "atlas_market_strength": self.atlas_market_strength,
            "confidence": self.confidence,
            "msrp_display": self.msrp_display,
            "last_sold_display": self.last_sold_display,
            "unit_scope": self.unit_scope,
            "unit_scope_is_caution": self.unit_scope_is_caution,
            "market_trend": self.market_trend,
            "atlas_market_trend": self.atlas_market_trend,
            "demand_tags": self.demand_tags,
            "links": {k: v.to_dict() for k, v in self.links.items()},
            "hearted": self.hearted,
            "hearted_at": self.hearted_at,
            "has_notes": self.has_notes,
            "has_override": self.has_override,
        }


@dataclass
class OverrideDetailViewModel:
    field_name: str
    atlas_value: Any
    user_value: Any
    reason: str | None
    updated_at: str

    def to_dict(self):
        return asdict(self)


@dataclass
class CardDetailsViewModel:
    opportunity_id: str
    why_bullets: list[str]
    risks: list[str]
    source_evidence_count: int
    overrides: list[OverrideDetailViewModel]
    opportunity_last_evaluated: str | None
    source_last_checked: str | None
    market_price_last_updated: str | None
    user_last_edited: str | None

    def to_dict(self):
        return {
            "opportunity_id": self.opportunity_id,
            "why_bullets": self.why_bullets,
            "risks": self.risks,
            "source_evidence_count": self.source_evidence_count,
            "overrides": [o.to_dict() for o in self.overrides],
            "opportunity_last_evaluated": self.opportunity_last_evaluated,
            "source_last_checked": self.source_last_checked,
            "market_price_last_updated": self.market_price_last_updated,
            "user_last_edited": self.user_last_edited,
        }


def build_card_view_model(
    opportunity,
    evaluation,
    override=None,
    image_record=None,
    user_links=None,
    hearted_item=None,
    note_count=0,
    now=None,
):
    """
    Builds the compact card. Never mutates any input. `override` is
    an OpportunityUserOverride or None; `hearted_item` a HeartedItem
    or None (its presence/absence is the ONLY thing hearting affects
    here - it never changes market_strength/confidence/anything else).
    """
    atlas_market_strength = classify_market_strength(opportunity, evaluation)
    market_strength = effective_value(
        atlas_market_strength, override.market_strength_override if override else None,
    )

    atlas_trend = classify_market_trend(opportunity)
    market_trend = effective_value(
        atlas_trend, override.market_trend_override if override else None,
    )

    demand_tags = select_demand_tags(
        opportunity, evaluation, override.demand_tags_override if override else None,
    )

    image = resolve_image(opportunity, override, image_record)

    unit_scope = resolve_unit_scope_label(opportunity)

    return ProductCardViewModel(
        opportunity_id=opportunity.opportunity_id,
        product_name=opportunity.product_name,
        image=image,
        updated_relative=format_relative_time(opportunity.last_verified_at or opportunity.discovered_at, now=now),
        market_strength=market_strength,
        market_strength_is_override=bool(override and override.market_strength_override is not None),
        atlas_market_strength=atlas_market_strength,
        confidence=classify_confidence(evaluation),
        msrp_display=format_money(opportunity.retail_price or opportunity.required_spend),
        last_sold_display=format_money(opportunity.recent_sold_price),
        unit_scope=unit_scope,
        unit_scope_is_caution=is_complete_set_mismatch(opportunity),
        market_trend=market_trend,
        atlas_market_trend=atlas_trend,
        demand_tags=demand_tags,
        links=resolve_links(opportunity, user_links),
        hearted=hearted_item is not None and not (hearted_item and hearted_item.is_archived()),
        hearted_at=hearted_item.hearted_at if hearted_item else None,
        has_notes=note_count > 0,
        has_override=bool(override and override.has_any_override()),
    )


def build_details_view_model(opportunity, evaluation, override=None, override_history=None, now=None):
    overrides = []
    if override:
        from collector_intelligence.dashboard_models import OVERRIDE_ATTRIBUTE_BY_FIELD
        atlas_values = {
            "market_strength": classify_market_strength(opportunity, evaluation),
            "market_trend": classify_market_trend(opportunity),
            "demand_tags": select_demand_tags(opportunity, evaluation),
            "collector_classification": None,
            "image": None,
            "tags": None,
        }
        for field_name, attribute_name in OVERRIDE_ATTRIBUTE_BY_FIELD.items():
            user_value = getattr(override, attribute_name)
            if user_value is not None:
                overrides.append(OverrideDetailViewModel(
                    field_name=field_name,
                    atlas_value=atlas_values.get(field_name),
                    user_value=user_value,
                    reason=override.reason,
                    updated_at=override.updated_at,
                ))

    return CardDetailsViewModel(
        opportunity_id=opportunity.opportunity_id,
        why_bullets=list(evaluation.positive_factors)[:6],
        risks=list(evaluation.negative_factors)[:6] + list(evaluation.warnings),
        source_evidence_count=len(opportunity.evidence or []),
        overrides=overrides,
        opportunity_last_evaluated=opportunity.last_verified_at,
        source_last_checked=opportunity.discovered_at,
        market_price_last_updated=opportunity.last_verified_at,
        user_last_edited=override.updated_at if override else None,
    )


# ---------------------------------------------------------------
# Hearted Items page row view model
# ---------------------------------------------------------------

@dataclass
class HeartedItemRowViewModel:
    hearted_item_id: str
    opportunity_id: str | None
    is_manual: bool
    product_name: str
    image: ImageViewModel
    market_strength: str
    status: str
    target_price_display: str
    quantity: int | None
    priority: str | None
    category: str | None
    tags: list[str]
    product_link: str | None
    ebay_sold_link: str | None
    hearted_at: str
    archived: bool
    has_notes: bool

    def to_dict(self):
        return {
            "hearted_item_id": self.hearted_item_id,
            "opportunity_id": self.opportunity_id,
            "is_manual": self.is_manual,
            "product_name": self.product_name,
            "image": self.image.to_dict(),
            "market_strength": self.market_strength,
            "status": self.status,
            "target_price_display": self.target_price_display,
            "quantity": self.quantity,
            "priority": self.priority,
            "category": self.category,
            "tags": self.tags,
            "product_link": self.product_link,
            "ebay_sold_link": self.ebay_sold_link,
            "hearted_at": self.hearted_at,
            "archived": self.archived,
            "has_notes": self.has_notes,
        }


def build_hearted_item_row(hearted_item, opportunity=None, evaluation=None, note_count=0):
    """
    Builds one Hearted Items page row. For an Atlas-linked item
    (opportunity + evaluation supplied), market_strength/image reuse
    the SAME classification functions as the opportunity card - no
    separate derivation. For a manual item, the user's own supplied
    fields are the only source of truth.
    """
    if hearted_item.opportunity_id and opportunity is not None:
        market_strength = classify_market_strength(opportunity, evaluation)
        image = resolve_image(opportunity)
        product_name = opportunity.product_name
        target_price = hearted_item.target_price
        product_link = opportunity.purchase_url
        ebay_sold_link = None
    else:
        market_strength = hearted_item.market_strength or "UNKNOWN"
        image = ImageViewModel(
            url=hearted_item.image_url or PLACEHOLDER_IMAGE_URL,
            alt_text=hearted_item.product_name or "Product image",
            source_label="User supplied" if hearted_item.image_url else None,
            is_placeholder=not bool(hearted_item.image_url),
        )
        product_name = hearted_item.product_name or "Untitled item"
        target_price = hearted_item.target_price
        product_link = hearted_item.product_link
        ebay_sold_link = hearted_item.ebay_sold_link

    return HeartedItemRowViewModel(
        hearted_item_id=hearted_item.id,
        opportunity_id=hearted_item.opportunity_id,
        is_manual=hearted_item.is_manual(),
        product_name=product_name,
        image=image,
        market_strength=market_strength,
        status=hearted_item.status,
        target_price_display=format_money(target_price),
        quantity=hearted_item.quantity,
        priority=hearted_item.priority,
        category=hearted_item.category,
        tags=list(hearted_item.tags or []),
        product_link=product_link,
        ebay_sold_link=ebay_sold_link,
        hearted_at=hearted_item.hearted_at,
        archived=hearted_item.is_archived(),
        has_notes=note_count > 0,
    )
