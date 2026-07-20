"""
Atlas v21 - Collector Intelligence Engine, Module 1: data foundation.

CollectorOpportunity represents a single collectible opportunity
(a product, drop, promo, or collaboration) across any ecosystem Atlas
tracks - not just Pokémon. This module intentionally contains no
scraping, no scoring heuristics, and no brand-specific logic: it is
only the structure, validation, deduplication, and human-readable
summary needed before any live source is connected.

Design rules enforced here:
- Scores are 0-100 or None. A missing score is never invented as a
  number; a caller must supply evidence-backed values.
- Market figures (prices, listing counts, velocities) default to
  None, not 0 or an assumed value, when unknown.
- Enum-shaped fields (primary_strategy, recommendation,
  acquisition_difficulty, demand_direction, source_type) are
  validated against collector_intelligence.enums and raise on an
  unrecognized value rather than silently accepting bad data.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from collector_intelligence.enums import (
    ENUM_FIELDS,
    coerce_enum_value,
)
from collector_intelligence.normalize import (
    compute_dedup_key,
    normalize_text,
)


SCORE_FIELDS = [
    "collector_score",
    "flip_score",
    "hold_score",
    "scarcity_score",
    "demand_score",
    "hype_score",
    "acquisition_score",
    "risk_score",
    "confidence_score",
    "opportunity_score",
]


def _validate_score(value, field_name):
    if value is None:
        return None

    try:
        numeric_value = float(value)

    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid {field_name!r}: {value!r} is not numeric"
        )

    if not (0 <= numeric_value <= 100):
        raise ValueError(
            f"Invalid {field_name!r}: {value!r} is outside the "
            "0-100 scale"
        )

    return numeric_value


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CollectorOpportunity:
    # --- Identity ---
    product_name: str
    brand: str
    normalized_product_name: str | None = None
    franchise: str | None = None
    product_line: str | None = None
    category: str | None = None
    subcategory: str | None = None
    collaboration_partner: str | None = None
    edition_name: str | None = None
    release_region: str | None = None

    # --- Release information ---
    announcement_date: str | None = None
    release_date: str | None = None
    release_time: str | None = None
    purchase_window_start: str | None = None
    purchase_window_end: str | None = None
    status: str | None = None

    # --- Purchase information ---
    retail_price: float | None = None
    required_spend: float | None = None
    currency: str | None = None
    purchase_method: str | None = None
    retailer: str | None = None
    purchase_limit: int | None = None
    membership_required: bool = False
    lottery_required: bool = False
    event_attendance_required: bool = False
    bundle_required: bool = False
    regional_exclusive: bool = False
    online_available: bool | None = None
    in_store_available: bool | None = None
    purchase_url: str | None = None

    # --- Collector characteristics ---
    limited_quantity: bool = False
    stated_quantity: int | None = None
    numbered: bool = False
    first_edition: bool = False
    first_collaboration: bool = False
    anniversary_release: bool = False
    exclusive_promo: bool = False
    exclusive_artwork: bool = False
    exclusive_character: bool = False
    event_exclusive: bool = False
    convention_exclusive: bool = False
    retailer_exclusive: bool = False
    region_exclusive: bool = False
    membership_exclusive: bool = False
    tournament_exclusive: bool = False
    artist_name: str | None = None
    character_names: list[str] = field(
        default_factory=list
    )
    set_or_series: str | None = None
    sealed_product: bool | None = None
    redeemable_reward: bool = False
    acquisition_difficulty: str | None = None

    # --- Market information ---
    current_market_price: float | None = None
    recent_sold_price: float | None = None
    estimated_market_price: float | None = None
    peak_market_price: float | None = None
    sales_velocity: float | None = None
    sellout_speed: str | None = None
    active_listing_count: int | None = None
    sold_listing_count: int | None = None
    demand_direction: str | None = None
    supply_direction: str | None = None

    # --- Scoring (0-100, None if not yet evidenced) ---
    collector_score: float | None = None
    flip_score: float | None = None
    hold_score: float | None = None
    scarcity_score: float | None = None
    demand_score: float | None = None
    hype_score: float | None = None
    acquisition_score: float | None = None
    risk_score: float | None = None
    confidence_score: float | None = None
    opportunity_score: float | None = None

    # --- Recommendation ---
    recommendation: str | None = None
    recommended_quantity: int | None = None
    target_buy_price: float | None = None
    target_sell_price: float | None = None
    estimated_profit: float | None = None
    estimated_roi_percent: float | None = None
    flip_time_horizon: str | None = None
    hold_time_horizon: str | None = None
    primary_strategy: str | None = None
    reasoning: list[str] = field(
        default_factory=list
    )
    risks: list[str] = field(
        default_factory=list
    )
    catalyst_signals: list[str] = field(
        default_factory=list
    )

    # --- Source tracking ---
    source_name: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    source_published_at: str | None = None
    discovered_at: str | None = None
    last_verified_at: str | None = None
    source_confidence: str | None = None
    raw_source_text: str | None = None
    evidence: list[dict[str, Any]] = field(
        default_factory=list
    )

    # --- Database / bookkeeping ---
    opportunity_id: str | None = None
    dedup_key: str | None = None
    raw_metadata: dict[str, Any] = field(
        default_factory=dict
    )
    score_explanation: dict[str, Any] = field(
        default_factory=dict
    )
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self):
        if not self.normalized_product_name:
            self.normalized_product_name = (
                normalize_text(self.product_name)
                or None
            )

        for field_name in SCORE_FIELDS:
            setattr(
                self,
                field_name,
                _validate_score(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        for (
            field_name,
            enum_cls,
        ) in ENUM_FIELDS.items():
            setattr(
                self,
                field_name,
                coerce_enum_value(
                    getattr(self, field_name),
                    enum_cls,
                    field_name,
                ),
            )

        if self.status is not None:
            self.status = (
                str(self.status).strip().lower()
                or None
            )

        if not self.opportunity_id:
            self.opportunity_id = str(uuid4())

        if not self.dedup_key:
            self.dedup_key = compute_dedup_key(
                brand=self.brand,
                franchise=self.franchise,
                product_name=self.product_name,
                collaboration_partner=(
                    self.collaboration_partner
                ),
                release_date=self.release_date,
                retailer=self.retailer,
            )

        if not self.discovered_at:
            self.discovered_at = _utc_now()

        if self.estimated_profit is None:
            spend, _ = self.resolved_spend()
            resale, _ = self.resolved_resale()

            if (
                spend is not None
                and resale is not None
            ):
                self.estimated_profit = round(
                    resale - spend,
                    2,
                )

        if (
            self.estimated_roi_percent is None
            and self.estimated_profit is not None
        ):
            spend, _ = self.resolved_spend()

            if spend:
                self.estimated_roi_percent = round(
                    (
                        self.estimated_profit
                        / spend
                    )
                    * 100,
                    2,
                )

    def resolved_spend(self):
        """
        Returns (value, field_name) for the best known "money out"
        figure, preferring an explicit required_spend (e.g. "had to
        spend $200 to qualify") over the plain retail_price.
        """
        if self.required_spend is not None:
            return (
                self.required_spend,
                "required_spend",
            )

        if self.retail_price is not None:
            return (
                self.retail_price,
                "retail_price",
            )

        return None, None

    def resolved_resale(self):
        """
        Returns (value, kind) for the best known resale figure.
        kind is "observed" for a real recorded sale/listing price,
        or "estimated" when only a modeled estimate exists - callers
        (like the summary formatter) use this to avoid presenting an
        estimate as a confirmed fact.
        """
        if self.recent_sold_price is not None:
            return (
                self.recent_sold_price,
                "observed",
            )

        if self.current_market_price is not None:
            return (
                self.current_market_price,
                "observed",
            )

        if self.peak_market_price is not None:
            return (
                self.peak_market_price,
                "observed",
            )

        if self.estimated_market_price is not None:
            return (
                self.estimated_market_price,
                "estimated",
            )

        return None, None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known_fields = {
            f
            for f in cls.__dataclass_fields__
        }

        filtered = {
            key: value
            for key, value in data.items()
            if key in known_fields
        }

        return cls(**filtered)
