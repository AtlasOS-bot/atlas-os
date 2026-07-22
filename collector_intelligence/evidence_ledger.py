"""
Atlas v21 - Module 4: evidence ledger construction.

Turns one source's Module 2 SignalDetectionResult (plus the partial
CollectorOpportunity Module 2 built from it) into a list of
EvidenceRecord - one per field-level claim - so every value the
aggregator ultimately chooses can be traced back to exactly which
source said what, and with what certainty.

This module also adds classification Module 2 does not attempt at
the signal level: which physical unit a price refers to (single item,
pack, box, case, complete set...), whether a price is a confirmed sale
or just an asking price, which phase a date belongs to (announcement,
release, restock...), and explicit textual negation of a boolean
characteristic. All of it is regex/keyword-based and local to Module 4
- Module 2 itself is not modified.
"""

import re

from collector_intelligence.aggregation_models import EvidenceRecord
from collector_intelligence.extraction import context_window
from collector_intelligence.normalize import normalize_text
from collector_intelligence.opportunity_builder import (
    BOOLEAN_SIGNAL_FIELDS,
    DUAL_BOOLEAN_SIGNAL_FIELDS,
)
from collector_intelligence.signals import SignalType


BOOLEAN_SIGNAL_FIELDS_BY_VALUE = {
    signal_type.value: field_name
    for signal_type, field_name in BOOLEAN_SIGNAL_FIELDS.items()
}

DUAL_BOOLEAN_SIGNAL_FIELDS_BY_VALUE = {
    signal_type.value: field_names
    for signal_type, field_names in DUAL_BOOLEAN_SIGNAL_FIELDS.items()
}

PRICE_SIGNAL_FIELDS = {
    SignalType.SPEND_REQUIREMENT.value: "required_spend",
    SignalType.RETAIL_PRICE.value: "retail_price",
}

QUANTITY_SIGNAL_FIELDS = {
    SignalType.LIMITED_QUANTITY.value: "stated_quantity",
    SignalType.PURCHASE_LIMIT.value: "purchase_limit",
}

STATUS_SIGNAL_VALUES = {
    SignalType.STATUS_SOLD_OUT.value: "sold_out",
    SignalType.STATUS_RESTOCKED.value: "restocked",
    SignalType.STATUS_LIVE.value: "live",
    SignalType.LOW_STOCK.value: "low_stock",
}


# ---------------------------------------------------------------
# Unit scope / grading classification
# ---------------------------------------------------------------

UNIT_SCOPE_KEYWORDS = [
    (
        "complete_set",
        ["complete set", "complete promo set", "full set", "entire set", "whole set"],
    ),
    ("case", ["per case", "a case of", "sealed case"]),
    ("box", ["booster box", "per box", "a box of", "display box"]),
    ("lot", ["lot of", "as a lot", "card lot"]),
    ("bundle", ["bundle"]),
    ("pack", ["per pack", "a pack", "single pack", "promotional pack", "promo pack"]),
    (
        "single_item",
        [
            "single card", "individual card", "per card", "one card",
            "single item", "per unit", "individual item",
        ],
    ),
]

GRADED_MARKERS = ["psa", "bgs", "cgc", "graded"]
UNGRADED_MARKERS = ["ungraded", "raw copy", "raw card", "non-graded"]


def classify_unit_scope(text):
    lowered = (text or "").lower()

    for scope, markers in UNIT_SCOPE_KEYWORDS:
        if any(marker in lowered for marker in markers):
            return scope

    return "unknown"


def classify_grading(text):
    lowered = (text or "").lower()

    # "ungraded" contains "graded" as a substring, so it must be
    # checked first - otherwise every ungraded mention would be
    # misclassified as graded.
    if any(marker in lowered for marker in UNGRADED_MARKERS):
        return "ungraded"

    if any(marker in lowered for marker in GRADED_MARKERS):
        return "graded"

    return None


# ---------------------------------------------------------------
# Sold vs. asking price classification
# ---------------------------------------------------------------

_SOLD_PATTERN = re.compile(r"\bsold\b(?!\s+out)")
ASKING_MARKERS = [
    "asking", "listed at", "listed for", "available for", "selling for",
    "up for", "asking price",
]


def classify_price_kind(text):
    lowered = (text or "").lower()

    if _SOLD_PATTERN.search(lowered):
        return "sold"

    if any(marker in lowered for marker in ASKING_MARKERS):
        return "asking"

    return "unknown"


# ---------------------------------------------------------------
# Date phase classification
# ---------------------------------------------------------------

DATE_PHASE_KEYWORDS = [
    ("announcement", ["announce", "reveal", "unveil"]),
    ("preorder", ["preorder", "pre-order"]),
    ("restock", ["restock"]),
    ("campaign_end", ["ends", "through", "until", "last day"]),
    ("event_start", ["event begins", "event starts", "doors open"]),
]


def classify_date_phase(text):
    lowered = (text or "").lower()

    for phase, markers in DATE_PHASE_KEYWORDS:
        if any(marker in lowered for marker in markers):
            return phase

    return "release"


# ---------------------------------------------------------------
# Explicit negation scanning (Module 4-local; Module 2's own
# negation handling *suppresses* a signal rather than emitting a
# negative-polarity one, so an official "this is not limited"
# statement would otherwise look identical to official silence).
# ---------------------------------------------------------------

NEGATION_CHECKS = {
    "limited_quantity": [
        r"\bnot\s+(?:a\s+)?limited\b",
        r"\bunlimited\s+(?:stock|quantity|supply|units|availability)\b",
    ],
    "exclusive_promo": [r"\bnot\s+(?:an?\s+)?exclusive\b"],
    "numbered": [r"\bnot\s+numbered\b"],
    "sealed_product": [r"\bnot\s+sealed\b"],
    "membership_required": [
        r"\bno\s+membership\s+required\b",
        r"\bwithout\s+(?:a\s+)?membership\b",
    ],
    "lottery_required": [r"\bno\s+lottery\b"],
}


def detect_explicit_negations(text):
    """
    Returns {field_name: matched_text} for each characteristic
    explicitly denied in `text` (e.g. "this product is not limited").
    """
    found = {}

    for field_name, patterns in NEGATION_CHECKS.items():
        for pattern in patterns:
            match = re.search(pattern, text or "", re.IGNORECASE)

            if match:
                found[field_name] = match.group(0)
                break

    return found


# ---------------------------------------------------------------
# Evidence record construction
# ---------------------------------------------------------------

def _record(
    source,
    field_name,
    value,
    detection=None,
    evidence_text=None,
    unit_scope=None,
    confidence=None,
    confirmed=None,
    estimated=None,
    rumored=None,
):
    if value is None:
        return None

    return EvidenceRecord(
        field_name=field_name,
        proposed_value=value,
        normalized_value=normalize_text(value) if isinstance(value, str) else value,
        source_name=source.source_name,
        source_type=source.source_type,
        source_url=source.source_url,
        source_published_at=source.published_at,
        evidence_text=(
            evidence_text
            if evidence_text is not None
            else (detection.evidence_text if detection else "")
        ),
        confidence=(
            confidence
            if confidence is not None
            else (detection.confidence if detection else 60.0)
        ),
        confirmed=(
            confirmed if confirmed is not None
            else (detection.confirmed if detection else True)
        ),
        estimated=(
            estimated if estimated is not None
            else (detection.estimated if detection else False)
        ),
        rumored=(
            rumored if rumored is not None
            else (detection.rumored if detection else False)
        ),
        accepted=False,
        rejection_reason=None,
        unit_scope=unit_scope,
        observed_at=source.discovered_at,
    )


def build_evidence_records(source, result, draft):
    """
    Returns list[EvidenceRecord] for every field-level claim this one
    source contributes, given its Module 2 SignalDetectionResult
    (`result`) and the partial CollectorOpportunity Module 2 built
    from it (`draft`).
    """
    records = []
    entities = result.extracted_entities
    text = source.full_text

    collaboration_detection = next(
        (
            detection
            for detection in result.detected_signals
            if detection.signal_type == SignalType.COLLABORATION.value
        ),
        None,
    )

    def add(record):
        if record is not None:
            records.append(record)

    # --- Identity ---
    add(_record(source, "product_name", draft.product_name, evidence_text=source.title))

    if entities.brand:
        add(_record(source, "brand", entities.brand, detection=collaboration_detection))

    if entities.franchise:
        add(_record(
            source, "franchise", entities.franchise, detection=collaboration_detection
        ))

    if entities.collaboration_partner:
        add(_record(
            source,
            "collaboration_partner",
            entities.collaboration_partner,
            detection=collaboration_detection,
        ))

    if entities.retailer:
        add(_record(
            source,
            "retailer",
            entities.retailer,
            evidence_text=f"retailer field on source: {entities.retailer}",
        ))

    # --- Per-detection evidence ---
    for detection in result.detected_signals:
        signal_type = detection.signal_type
        window = context_window(
            text,
            detection.evidence_start or 0,
            detection.evidence_end or 0,
            radius=60,
        ) if detection.evidence_start is not None else ""

        if signal_type in PRICE_SIGNAL_FIELDS:
            field_name = PRICE_SIGNAL_FIELDS[signal_type]
            unit_scope = (
                "complete_set"
                if detection.notes and "complete set" in detection.notes.lower()
                else classify_unit_scope(window)
            )
            add(_record(
                source, field_name, detection.extracted_value,
                detection=detection, unit_scope=unit_scope,
            ))
            continue

        if signal_type == SignalType.OBSERVED_RESALE_PRICE.value:
            unit_scope = (
                "complete_set"
                if detection.notes and "complete set" in detection.notes.lower()
                else classify_unit_scope(window)
            )
            price_kind = classify_price_kind(window)
            grading = classify_grading(window)

            if price_kind == "sold":
                target_field = "recent_sold_price"
            elif price_kind == "asking":
                target_field = "estimated_market_price"
            else:
                target_field = "current_market_price"

            add(_record(
                source, target_field, detection.extracted_value,
                detection=detection, unit_scope=unit_scope,
            ))

            if grading:
                grading_record = _record(
                    source, f"{target_field}__grading", grading,
                    detection=detection, evidence_text=window,
                )
                add(grading_record)

            price_kind_record = _record(
                source, f"{target_field}__price_kind", price_kind,
                detection=detection, evidence_text=window,
            )
            add(price_kind_record)
            continue

        if signal_type in QUANTITY_SIGNAL_FIELDS:
            add(_record(
                source, QUANTITY_SIGNAL_FIELDS[signal_type],
                detection.extracted_value, detection=detection,
            ))
            continue

        if signal_type == SignalType.PROMOTIONAL_PACK.value and detection.extracted_value:
            add(_record(
                source, "pack_quantity_note",
                f"{detection.extracted_value} {detection.extracted_unit or 'packs'}",
                detection=detection,
            ))
            continue

        if signal_type == SignalType.RELEASE_DATE.value:
            # A tight radius here on purpose: a wider window (like the
            # one used for price/unit-scope context) can pick up a
            # phase word that's actually describing a DIFFERENT date
            # mentioned nearby in the same short sentence/paragraph.
            narrow_window = context_window(
                text,
                detection.evidence_start or 0,
                detection.evidence_end or 0,
                radius=35,
            ) if detection.evidence_start is not None else ""
            phase = classify_date_phase(narrow_window)
            field_name = "announcement_date" if phase == "announcement" else "release_date"
            add(_record(source, field_name, detection.evidence_text, detection=detection))
            continue

        if signal_type == SignalType.RELEASE_TIME.value:
            add(_record(source, "release_time", detection.evidence_text, detection=detection))
            continue

        if signal_type == SignalType.PURCHASE_WINDOW.value and isinstance(
            detection.extracted_value, dict
        ):
            add(_record(
                source, "purchase_window_start",
                detection.extracted_value.get("start"), detection=detection,
            ))
            add(_record(
                source, "purchase_window_end",
                detection.extracted_value.get("end"), detection=detection,
            ))
            continue

        if signal_type in STATUS_SIGNAL_VALUES:
            add(_record(
                source, "status", STATUS_SIGNAL_VALUES[signal_type], detection=detection,
            ))
            continue

        boolean_field = BOOLEAN_SIGNAL_FIELDS_BY_VALUE.get(signal_type)
        if boolean_field:
            add(_record(source, boolean_field, True, detection=detection))
            continue

        dual_fields = DUAL_BOOLEAN_SIGNAL_FIELDS_BY_VALUE.get(signal_type)
        if dual_fields:
            for field_name in dual_fields:
                add(_record(source, field_name, True, detection=detection))
            continue

    # --- Explicit negation scan (Module 4-local) ---
    for field_name, matched_text in detect_explicit_negations(text).items():
        add(_record(
            source, field_name, False,
            evidence_text=matched_text, confidence=85.0,
            confirmed=True, estimated=False, rumored=False,
        ))

    return records
