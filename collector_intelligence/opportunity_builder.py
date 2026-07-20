"""
Converts a Module 2 SignalDetectionResult into a partial Module 1
CollectorOpportunity.

This module only transcribes what extraction.py/detector.py already
found - it never invents a score, a recommendation, or a strategy.
Fields like flip_score, hold_score, collector_score, recommendation,
primary_strategy, and acquisition_difficulty are judgment calls that
belong to a later scoring stage, so this builder leaves them unset
unless the caller passes them in explicitly via `overrides`.
"""

from collector_intelligence.models import CollectorOpportunity
from collector_intelligence.signals import SignalType


class InsufficientIdentityError(ValueError):
    """Raised when a SignalDetectionResult has no usable product
    identity (no product_name and no title to fall back on, or no
    brand/franchise/collaboration_partner)."""


STATUS_SIGNAL_PRIORITY = [
    (SignalType.STATUS_SOLD_OUT, "sold_out"),
    (SignalType.STATUS_RESTOCKED, "restocked"),
    (SignalType.LOW_STOCK, "low_stock"),
    (SignalType.STATUS_LIVE, "live"),
]

BOOLEAN_SIGNAL_FIELDS = {
    SignalType.EXCLUSIVE_PROMO: "exclusive_promo",
    SignalType.NUMBERED_RELEASE: "numbered",
    SignalType.FIRST_EDITION: "first_edition",
    SignalType.FIRST_COLLABORATION: "first_collaboration",
    SignalType.ANNIVERSARY: "anniversary_release",
    SignalType.EXCLUSIVE_ARTWORK: "exclusive_artwork",
    SignalType.EXCLUSIVE_CHARACTER: "exclusive_character",
    SignalType.EVENT_EXCLUSIVE: "event_exclusive",
    SignalType.CONVENTION_EXCLUSIVE: "convention_exclusive",
    SignalType.TOURNAMENT_EXCLUSIVE: "tournament_exclusive",
    SignalType.RETAILER_EXCLUSIVE: "retailer_exclusive",
    SignalType.REGION_EXCLUSIVE: "region_exclusive",
    SignalType.BUNDLE_REQUIRED: "bundle_required",
    SignalType.REDEEMABLE_REWARD: "redeemable_reward",
    SignalType.SEALED_PRODUCT: "sealed_product",
}

# Signals that set two related booleans at once (a specific
# exclusivity flag plus the broader purchase-requirement flag it
# implies).
DUAL_BOOLEAN_SIGNAL_FIELDS = {
    SignalType.MEMBERSHIP_EXCLUSIVE: (
        "membership_exclusive",
        "membership_required",
    ),
    SignalType.LOTTERY_REQUIRED: (
        "lottery_required",
        "lottery_required",
    ),
    SignalType.EVENT_ATTENDANCE_REQUIRED: (
        "event_attendance_required",
        "event_attendance_required",
    ),
}

CATALYST_SIGNAL_TYPES = {
    SignalType.COLLABORATION,
    SignalType.EXCLUSIVE_PROMO,
    SignalType.ANNIVERSARY,
    SignalType.FIRST_EDITION,
    SignalType.FIRST_COLLABORATION,
    SignalType.LIMITED_QUANTITY,
    SignalType.NUMBERED_RELEASE,
    SignalType.RAPID_SELLOUT,
    SignalType.HIGH_DEMAND,
    SignalType.RISING_DEMAND,
    SignalType.SURGING_DEMAND,
    SignalType.COMMUNITY_HYPE,
    SignalType.LOTTERY_REQUIRED,
    SignalType.MEMBERSHIP_EXCLUSIVE,
    SignalType.EVENT_EXCLUSIVE,
    SignalType.CONVENTION_EXCLUSIVE,
    SignalType.TOURNAMENT_EXCLUSIVE,
}

RISK_SIGNAL_TYPES = {
    SignalType.RISK_WARNING,
    SignalType.RUMOR,
    SignalType.HIGH_ACQUISITION_DIFFICULTY,
}


def _first(result, signal_type):
    matches = result.signals_of_type(signal_type)
    return matches[0] if matches else None


def _resolve_product_name(result):
    entities = result.extracted_entities
    source = result.raw_source

    if entities.product_name:
        return entities.product_name

    if source is not None and getattr(
        source, "title", None
    ):
        return source.title

    return None


def _resolve_brand(result):
    entities = result.extracted_entities

    return (
        entities.brand
        or entities.franchise
        or entities.collaboration_partner
    )


def _resolve_status(result):
    for signal_type, status in (
        STATUS_SIGNAL_PRIORITY
    ):
        if result.has_signal(signal_type):
            return status

    return None


def _resolve_demand_direction(result):
    if result.has_signal(
        SignalType.SURGING_DEMAND
    ):
        return "SURGING"

    if result.has_signal(
        SignalType.RISING_DEMAND
    ):
        return "RISING"

    return None


def _resolve_price_fields(result):
    fields = {}

    spend_signal = _first(
        result, SignalType.SPEND_REQUIREMENT
    )

    if spend_signal:
        fields["required_spend"] = (
            spend_signal.extracted_value
        )
        fields["currency"] = (
            spend_signal.extracted_unit
        )

    retail_signal = _first(
        result, SignalType.RETAIL_PRICE
    )

    if retail_signal:
        fields["retail_price"] = (
            retail_signal.extracted_value
        )
        fields.setdefault(
            "currency",
            retail_signal.extracted_unit,
        )

    resale_signal = _first(
        result, SignalType.OBSERVED_RESALE_PRICE
    )

    if resale_signal:
        fields["recent_sold_price"] = (
            resale_signal.extracted_value
        )
        fields.setdefault(
            "currency", resale_signal.extracted_unit
        )

    return fields


def _resolve_quantity_fields(result):
    fields = {}

    limited_signal = _first(
        result, SignalType.LIMITED_QUANTITY
    )

    if limited_signal:
        fields["limited_quantity"] = True
        fields["stated_quantity"] = (
            limited_signal.extracted_value
        )

    purchase_limit_signal = _first(
        result, SignalType.PURCHASE_LIMIT
    )

    if purchase_limit_signal:
        fields["purchase_limit"] = (
            purchase_limit_signal.extracted_value
        )

    return fields


def _resolve_release_fields(result):
    fields = {}

    release_date_signal = _first(
        result, SignalType.RELEASE_DATE
    )

    if release_date_signal:
        fields["release_date"] = (
            release_date_signal.evidence_text
        )

    release_time_signal = _first(
        result, SignalType.RELEASE_TIME
    )

    if release_time_signal:
        fields["release_time"] = (
            release_time_signal.evidence_text
        )

    window_signal = _first(
        result, SignalType.PURCHASE_WINDOW
    )

    if window_signal and isinstance(
        window_signal.extracted_value, dict
    ):
        fields["purchase_window_start"] = (
            window_signal.extracted_value.get(
                "start"
            )
        )
        fields["purchase_window_end"] = (
            window_signal.extracted_value.get(
                "end"
            )
        )

    sellout_signal = _first(
        result, SignalType.RAPID_SELLOUT
    )

    if (
        sellout_signal
        and sellout_signal.extracted_value
    ):
        fields["sellout_speed"] = (
            f"within {sellout_signal.extracted_value} "
            f"{sellout_signal.extracted_unit}"
        )

    return fields


def _resolve_boolean_fields(result):
    fields = {}

    for signal_type, field_name in (
        BOOLEAN_SIGNAL_FIELDS.items()
    ):
        if result.has_signal(signal_type):
            fields[field_name] = True

    for (
        signal_type,
        field_names,
    ) in DUAL_BOOLEAN_SIGNAL_FIELDS.items():
        if result.has_signal(signal_type):
            for field_name in field_names:
                fields[field_name] = True

    return fields


def _build_catalyst_signals(result):
    catalysts = []

    for detection in result.detected_signals:
        if (
            detection.signal_type
            in {
                signal.value
                for signal in CATALYST_SIGNAL_TYPES
            }
            and detection.evidence_text
        ):
            catalysts.append(
                detection.evidence_text.strip()
            )

    # Preserve order, drop exact duplicates.
    seen = set()
    deduped = []

    for catalyst in catalysts:
        if catalyst not in seen:
            seen.add(catalyst)
            deduped.append(catalyst)

    return deduped


def _build_risks(result):
    risks = []

    for detection in result.detected_signals:
        if (
            detection.signal_type
            in {
                signal.value
                for signal in RISK_SIGNAL_TYPES
            }
        ):
            text = (
                detection.notes
                or detection.evidence_text
            )

            if text and text not in risks:
                risks.append(text.strip())

    return risks


def build_partial_opportunity(
    result, overrides=None
):
    """
    Builds a CollectorOpportunity from a SignalDetectionResult.

    Raises InsufficientIdentityError if neither the result's
    extracted entities nor the raw source's title provide enough
    identity to populate the required product_name/brand fields, and
    `overrides` doesn't supply them either.
    """
    overrides = dict(overrides or {})

    product_name = overrides.get(
        "product_name"
    ) or _resolve_product_name(result)

    brand = overrides.get(
        "brand"
    ) or _resolve_brand(result)

    if not product_name or not brand:
        raise InsufficientIdentityError(
            "Cannot build a CollectorOpportunity: "
            "no product_name/brand could be resolved "
            "from extracted entities, the source "
            "title, or overrides."
        )

    entities = result.extracted_entities
    source = result.raw_source

    fields = {
        "product_name": product_name,
        "brand": brand,
        "franchise": entities.franchise,
        "collaboration_partner": (
            entities.collaboration_partner
        ),
        "retailer": entities.retailer,
        "character_names": list(
            entities.character_names
        ),
        "artist_name": entities.artist_name,
        "release_region": entities.region,
        "set_or_series": entities.set_or_series,
    }

    status = _resolve_status(result)
    if status:
        fields["status"] = status

    demand_direction = _resolve_demand_direction(
        result
    )
    if demand_direction:
        fields["demand_direction"] = (
            demand_direction
        )

    fields.update(_resolve_price_fields(result))
    fields.update(
        _resolve_quantity_fields(result)
    )
    fields.update(
        _resolve_release_fields(result)
    )
    fields.update(
        _resolve_boolean_fields(result)
    )

    catalyst_signals = _build_catalyst_signals(
        result
    )
    if catalyst_signals:
        fields["catalyst_signals"] = (
            catalyst_signals
        )

    risks = _build_risks(result)
    if risks:
        fields["risks"] = risks

    if source is not None:
        fields["source_name"] = (
            source.source_name
        )
        fields["source_type"] = (
            source.source_type
        )
        fields["source_url"] = source.source_url
        fields["source_published_at"] = (
            source.published_at
        )
        fields["discovered_at"] = (
            source.discovered_at
        )
        fields["raw_source_text"] = (
            source.full_text
        )

    fields["evidence"] = [
        detection.to_dict()
        for detection in result.detected_signals
    ]

    raw_metadata = dict(
        source.raw_metadata
        if source is not None
        else {}
    )
    raw_metadata["collector_relevance_score"] = (
        result.collector_relevance_score
    )
    raw_metadata["overall_signal_confidence"] = (
        result.overall_signal_confidence
    )
    fields["raw_metadata"] = raw_metadata

    # Overrides always win, including over required identity fields
    # already resolved above.
    fields.update(overrides)

    return CollectorOpportunity.from_dict(fields)
