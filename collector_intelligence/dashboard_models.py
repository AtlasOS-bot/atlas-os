"""
Atlas v21 - Module 8: dashboard user-data models.

These models hold PERSONAL, USER-GENERATED data layered on top of
Modules 1-7's CollectorOpportunity/OpportunityEvaluation - hearts,
notes, manual market overrides, and manually-entered items. Nothing
here is evidence, and nothing here is scored:

- Notes never enter Module 2 signal detection or Module 3 scoring.
- Overrides never mutate a CollectorOpportunity's own fields, its
  evidence ledger, or its source records - they live in a completely
  separate table and are applied only at DISPLAY time (see
  dashboard_view.py's effective_market_strength()).
- Hearting an item never changes its market strength or any Atlas
  score.

Every model is a plain dataclass with to_dict()/from_dict() so rows
round-trip cleanly to/from Supabase's REST JSON, matching every other
persistence model in this codebase (CollectorOpportunity, etc.).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _new_id():
    return str(uuid4())


VALID_MARKET_STRENGTHS = ("STRONG", "MEDIUM", "WEAK", "UNKNOWN")
VALID_MARKET_TRENDS = ("RISING", "STABLE", "FALLING", "UNKNOWN")
VALID_CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")

VALID_HEARTED_STATUSES = (
    "SAVED", "APPROVED", "DENIED", "PURCHASED", "SOLD", "ARCHIVED",
)

# Matches the LINKS section: 5 distinct, never-conflated link types -
# "Never label active asking listings as sold listings."
VALID_LINK_TYPES = (
    "product", "official_source", "ebay_sold", "current_listings", "evidence",
)

VALID_LINK_OWNER_TYPES = ("opportunity", "hearted_item")

# Fields an OpportunityUserOverride is allowed to touch - deliberately
# limited to presentation/classification concerns. There is no
# override field for price, evidence, or scores: those stay Atlas's.
OVERRIDABLE_FIELDS = (
    "market_strength", "market_trend", "demand_tags",
    "collector_classification", "image", "tags",
)

# logical field name -> actual OpportunityUserOverride attribute name.
# Most follow "{field}_override", but "image" is stored as
# "image_override_url" (it's a URL, not a classification value).
OVERRIDE_ATTRIBUTE_BY_FIELD = {
    name: ("image_override_url" if name == "image" else f"{name}_override")
    for name in OVERRIDABLE_FIELDS
}


def _mint_from_dict(cls, data):
    known = {f for f in cls.__dataclass_fields__}
    return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class OpportunityUserOverride:
    """
    One live row per opportunity - the user's CURRENT override state.
    Every *_override field is None when "use Atlas's assessment."
    Never stores a computed effective_* value (see dashboard_view.py).
    """
    id: str = field(default_factory=_new_id)
    opportunity_id: str = ""

    market_strength_override: str | None = None
    market_trend_override: str | None = None
    demand_tags_override: list[str] | None = None
    collector_classification_override: str | None = None
    image_override_url: str | None = None
    tags_override: list[str] | None = None

    reason: str | None = None

    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _mint_from_dict(cls, data)

    def has_any_override(self):
        return any(
            getattr(self, attribute_name) is not None
            for attribute_name in OVERRIDE_ATTRIBUTE_BY_FIELD.values()
        )


@dataclass
class OpportunityOverrideHistory:
    """Append-only. One row per change to any single override field,
    so 'what did Atlas say, what did the user set, and why' is always
    answerable even after Atlas's live assessment later changes."""
    id: str = field(default_factory=_new_id)
    opportunity_id: str = ""
    field_name: str = ""  # one of OVERRIDABLE_FIELDS
    atlas_value_snapshot: Any = None
    previous_override_value: Any = None
    new_override_value: Any = None
    reason: str | None = None
    changed_at: str = field(default_factory=_utc_now)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _mint_from_dict(cls, data)


@dataclass
class OpportunityNote:
    """'My Notes' on an Atlas opportunity. Never evidence, never fed
    back into detection/scoring."""
    id: str = field(default_factory=_new_id)
    opportunity_id: str = ""
    body: str = ""
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _mint_from_dict(cls, data)

    def was_edited(self):
        return self.updated_at != self.created_at


@dataclass
class HeartedItem:
    """
    The user's personal 'Hearted Items' list. One table for both
    kinds of entry:

    - opportunity_id set    -> a hearted Atlas card. Display fields
      (name/image/price/etc.) are read from the CollectorOpportunity
      + its overrides; the manual-only fields below are ignored.
    - opportunity_id is None -> a fully manual item. The manual-only
      fields below are the entry's only source of truth; it never
      needs an Atlas opportunity to exist.
    """
    id: str = field(default_factory=_new_id)
    opportunity_id: str | None = None

    status: str = "SAVED"
    target_price: float | None = None
    quantity: int | None = None
    priority: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)

    # Manual-only fields - populated only when opportunity_id is None.
    product_name: str | None = None
    image_url: str | None = None
    product_link: str | None = None
    ebay_sold_link: str | None = None
    msrp: float | None = None
    last_sold_price: float | None = None
    market_strength: str | None = None

    hearted_at: str = field(default_factory=_utc_now)
    archived_at: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _mint_from_dict(cls, data)

    def is_manual(self):
        return self.opportunity_id is None

    def is_archived(self):
        return self.archived_at is not None


@dataclass
class HeartedItemNote:
    """Notes scoped to the personal-list entry itself (e.g. purchase
    tracking), distinct from OpportunityNote which is about the
    product generally."""
    id: str = field(default_factory=_new_id)
    hearted_item_id: str = ""
    body: str = ""
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _mint_from_dict(cls, data)

    def was_edited(self):
        return self.updated_at != self.created_at


@dataclass
class OpportunityImage:
    """Atlas-sourced image evidence for one opportunity - never a user
    value (see OpportunityUserOverride.image_override_url for that)."""
    id: str = field(default_factory=_new_id)
    opportunity_id: str = ""
    primary_image_url: str | None = None
    image_source_url: str | None = None
    image_source_name: str | None = None
    image_alt_text: str | None = None
    image_last_verified_at: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _mint_from_dict(cls, data)


@dataclass
class UserExternalLink:
    """
    Generic user-added/overridden link, for either an opportunity or
    a hearted item. Covers all 5 LINKS types uniformly rather than a
    fixed column per link type.
    """
    id: str = field(default_factory=_new_id)
    owner_type: str = "opportunity"  # "opportunity" | "hearted_item"
    owner_id: str = ""
    link_type: str = "product"  # one of VALID_LINK_TYPES
    url: str = ""
    label: str | None = None
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _mint_from_dict(cls, data)
