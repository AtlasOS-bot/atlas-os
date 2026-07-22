"""
Atlas v21 - Module 4: aggregation/finalization configuration.

Every numeric rule the aggregator uses lives here so behavior can be
tuned without touching merge logic.
"""

from dataclasses import dataclass, field


# Base authority ranking when a field has no field-specific priority
# list below. Higher wins.
DEFAULT_SOURCE_TYPE_WEIGHTS = {
    "OFFICIAL": 90,
    "RETAILER": 80,
    "PRESS_RELEASE": 75,
    "EVENT": 70,
    "MARKETPLACE": 55,
    "NEWS": 50,
    "COMMUNITY": 30,
    "SOCIAL": 20,
    "OTHER": 10,
}

_IDENTITY_ORDER = [
    "OFFICIAL", "RETAILER", "PRESS_RELEASE", "EVENT", "NEWS",
    "MARKETPLACE", "COMMUNITY", "SOCIAL", "OTHER",
]

_RETAILER_STRONG_ORDER = [
    "RETAILER", "OFFICIAL", "EVENT", "PRESS_RELEASE", "NEWS",
    "MARKETPLACE", "COMMUNITY", "SOCIAL", "OTHER",
]

_MARKET_EVIDENCE_ORDER = [
    "MARKETPLACE", "RETAILER", "NEWS", "COMMUNITY", "SOCIAL",
    "OFFICIAL", "EVENT", "PRESS_RELEASE", "OTHER",
]

# Fields where OFFICIAL sources set the terms of the product/campaign.
_IDENTITY_FIELDS = [
    "product_name", "brand", "franchise", "collaboration_partner",
    "edition_name", "release_region", "category", "subcategory",
    "set_or_series", "release_date", "release_time",
    "purchase_window_start", "purchase_window_end", "announcement_date",
    "stated_quantity", "numbered", "first_edition", "first_collaboration",
    "anniversary_release", "exclusive_promo", "exclusive_artwork",
    "exclusive_character", "event_exclusive", "convention_exclusive",
    "tournament_exclusive", "membership_exclusive", "membership_required",
    "lottery_required", "event_attendance_required", "bundle_required",
    "sealed_product", "redeemable_reward", "required_spend",
    "purchase_method",
]

# Fields where a retailer (who actually sells/stocks the item) is the
# strongest source.
_RETAILER_STRONG_FIELDS = [
    "retail_price", "purchase_limit", "status", "online_available",
    "in_store_available", "retailer_exclusive", "region_exclusive",
    "regional_exclusive", "purchase_url", "retailer",
]

# Fields where marketplace observations are the primary evidence.
_MARKET_EVIDENCE_FIELDS = [
    "recent_sold_price", "current_market_price", "estimated_market_price",
]


def _default_field_source_priority():
    priority = {}

    for name in _IDENTITY_FIELDS:
        priority[name] = list(_IDENTITY_ORDER)

    for name in _RETAILER_STRONG_FIELDS:
        priority[name] = list(_RETAILER_STRONG_ORDER)

    for name in _MARKET_EVIDENCE_FIELDS:
        priority[name] = list(_MARKET_EVIDENCE_ORDER)

    return priority


@dataclass
class FinalizationConfig:
    source_type_weights: dict = field(
        default_factory=lambda: dict(DEFAULT_SOURCE_TYPE_WEIGHTS)
    )

    field_source_priority: dict = field(
        default_factory=_default_field_source_priority
    )

    # Fraction of comparable identity fields that must agree for two
    # drafts to be considered the same opportunity.
    identity_match_threshold: float = 0.6

    # A status observation older than this (relative to the newest
    # observation in the same tier) is flagged as possibly stale in
    # the finalized summary, not silently trusted as current.
    stale_status_age_hours: float = 168.0

    # A retail/spend value differing by more than this percentage from
    # another candidate is a "material" price conflict.
    material_price_change_percent: float = 15.0

    # opportunity_score/recommendation/strategy changes at or above
    # this are "material" in a change summary.
    score_change_significance: float = 10.0

    # A sold-price observation whose resale/spend ratio exceeds this
    # multiplier, reported only by weak (COMMUNITY/SOCIAL/OTHER)
    # sources, is treated as an extreme claim requiring review.
    extreme_resale_multiplier: float = 15.0

    # A sold observation deviating from the median of other sold
    # observations by more than this ratio is an outlier.
    price_outlier_ratio: float = 2.5

    # Below this many consistent sold observations, market confidence
    # is capped (a single data point is never "confident").
    minimum_market_observations: int = 2

    # Whether a merge may overwrite a field the caller populated
    # manually on an existing_opportunity (source_type is None/absent
    # on manually entered data).
    allow_manual_value_overwrite: bool = False

    # Whether an "asking" (not confirmed sold) price observation may
    # populate estimated_market_price at all.
    allow_asking_price_as_market_estimate: bool = True

    conflict_severity_thresholds: dict = field(
        default_factory=lambda: {
            "price_material_percent": 15.0,
            "price_high_percent": 50.0,
            "price_critical_percent": 200.0,
        }
    )
