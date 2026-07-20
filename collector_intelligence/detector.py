"""
Module 2 orchestration: turns a RawSourceInput into a
SignalDetectionResult using only the deterministic primitives in
extraction.py. No network calls, no AI/embeddings.
"""

import re

from collector_intelligence.enums import SourceType
from collector_intelligence.extraction import (
    classify_certainty,
    classify_price_context,
    certainty_flags,
    find_collaboration,
    find_currency_amounts,
    find_dates,
    find_limited_quantity,
    find_numbered_release,
    find_pack_quantity,
    find_purchase_limit,
    find_purchase_window,
    find_release_time,
    find_sellout_duration,
    has_collaboration_keyword,
    has_unlimited_override,
    is_locally_negated,
    mentions_complete_set,
)
from collector_intelligence.signals import (
    ExtractedEntities,
    SignalDetection,
    SignalDetectionResult,
    SignalType,
)


DEFAULT_RELEVANCE_THRESHOLD = 35


# ---------------------------------------------------------------
# Keyword-only signal dictionary
#
# Each entry: signal_type -> list of (regex, base_confidence).
# A match is discarded if a negation trigger word appears in the
# few words immediately before it.
# ---------------------------------------------------------------

def _kw(pattern):
    return re.compile(pattern, re.IGNORECASE)


KEYWORD_SIGNALS = {
    SignalType.ANNIVERSARY: [
        (_kw(r"\b\d+(?:st|nd|rd|th)\s+anniversary\b"), 85),
        (_kw(r"\banniversary\s+(?:edition|release|product|collection)\b"), 80),
        (_kw(r"\banniversary\b"), 60),
    ],
    SignalType.EXCLUSIVE_PROMO: [
        (_kw(r"\bexclusive\s+promo(?:tional)?\b"), 85),
        (_kw(r"\bexclusive\s+promotional\s+(?:card\s+)?packs?\b"), 90),
    ],
    SignalType.PROMOTIONAL_PACK: [
        (_kw(r"\bpromotional\s+(?:card\s+)?packs?\b"), 80),
        (_kw(r"\bpromo\s+packs?\b"), 75),
        (_kw(r"\bpromo\s+cards?\b"), 65),
    ],
    SignalType.FIRST_EDITION: [
        (_kw(r"\bfirst\s+edition\b"), 85),
    ],
    SignalType.FIRST_COLLABORATION: [
        (_kw(r"\bfirst[\s-](?:ever\s+)?collaboration\b"), 85),
        (_kw(r"\bfirst[\s-]time\s+collaborat\w*\b"), 80),
    ],
    SignalType.EXCLUSIVE_ARTWORK: [
        (_kw(r"\bexclusive\s+art(?:work)?\b"), 80),
        (_kw(r"\bunique\s+artwork\b"), 70),
    ],
    SignalType.EXCLUSIVE_CHARACTER: [
        (_kw(r"\bexclusive\s+character\b"), 80),
        (_kw(r"\bcharacter[\s-]exclusive\b"), 80),
    ],
    SignalType.EVENT_EXCLUSIVE: [
        (_kw(r"\bevent[\s-]exclusive\b"), 85),
        (_kw(r"\bonly\s+available\s+at\s+the\s+event\b"), 85),
        (_kw(r"\bexclusive\s+to\s+(?:the\s+)?event\b"), 80),
    ],
    SignalType.CONVENTION_EXCLUSIVE: [
        (_kw(r"\bconvention[\s-]exclusive\b"), 85),
        (_kw(r"\bcon[\s-]exclusive\b"), 75),
    ],
    SignalType.TOURNAMENT_EXCLUSIVE: [
        (_kw(r"\btournament[\s-]exclusive\b"), 85),
        (_kw(r"\btournament[\s-]only\b"), 80),
        (_kw(r"\btournament\s+promo\b"), 75),
    ],
    SignalType.RETAILER_EXCLUSIVE: [
        (_kw(r"\bretailer[\s-]exclusive\b"), 85),
        (_kw(r"\bavailable\s+exclusively\s+at\b"), 80),
        (_kw(r"\bparticipating\s+[A-Z][\w'&]*\s+locations\b"), 75),
        (_kw(r"\bexclusive\s+to\s+[A-Z][\w'&]*\b"), 65),
    ],
    SignalType.REGION_EXCLUSIVE: [
        (_kw(r"\bregion(?:al)?[\s-]exclusive\b"), 80),
        (_kw(r"\bavailable\s+only\s+in\b"), 65),
    ],
    SignalType.MEMBERSHIP_EXCLUSIVE: [
        (_kw(r"\bmembers?[\s-]only\b"), 85),
        (_kw(r"\bmembership[\s-](?:required|exclusive)\b"), 85),
        (_kw(r"\bfor\s+members\s+only\b"), 85),
    ],
    SignalType.LOTTERY_REQUIRED: [
        (_kw(r"\blottery\b"), 80),
        (_kw(r"\braffle\b"), 75),
        (_kw(r"\bentered\s+into\s+a\s+drawing\b"), 70),
        (_kw(r"\bdrawing\s+to\s+win\b"), 70),
    ],
    SignalType.EVENT_ATTENDANCE_REQUIRED: [
        (_kw(r"\bmust\s+attend\b"), 80),
        (_kw(r"\battendance\s+required\b"), 85),
        (_kw(r"\bonly\s+available\s+to\s+attendees\b"), 85),
        (_kw(r"\bin[\s-]person\s+only\b"), 70),
    ],
    SignalType.BUNDLE_REQUIRED: [
        (_kw(r"\bbundle\s+required\b"), 85),
        (_kw(r"\bonly\s+available\s+as\s+a\s+bundle\b"), 85),
        (_kw(r"\bmust\s+(?:purchase|buy)\s+as\s+a\s+bundle\b"), 80),
        (_kw(r"\bbundled\s+with\b"), 60),
    ],
    SignalType.REDEEMABLE_REWARD: [
        (_kw(r"\bredeem(?:able)?\b"), 70),
        (_kw(r"\bredemption\b"), 70),
        (_kw(r"\breward\s+for\b"), 60),
        (_kw(r"\breceive\s+as\s+a\s+reward\b"), 70),
    ],
    SignalType.STATUS_LIVE: [
        (_kw(r"\bavailable\s+now\b"), 75),
        (_kw(r"\bnow\s+available\b"), 75),
        (_kw(r"\bon\s+sale\s+now\b"), 75),
        (_kw(r"\blaunches\s+today\b"), 70),
    ],
    SignalType.STATUS_SOLD_OUT: [
        (_kw(r"\bsold\s+out\b"), 85),
        (_kw(r"\bout\s+of\s+stock\b"), 80),
    ],
    SignalType.STATUS_RESTOCKED: [
        (_kw(r"\brestocked\b"), 80),
        (_kw(r"\bback\s+in\s+stock\b"), 80),
        (_kw(r"\brestock\s+announced\b"), 80),
    ],
    SignalType.LOW_STOCK: [
        (_kw(r"\blow\s+stock\b"), 75),
        (_kw(r"\bfew\s+remaining\b"), 65),
        (_kw(r"\balmost\s+sold\s+out\b"), 70),
        (_kw(r"\blimited\s+stock\s+remaining\b"), 70),
    ],
    SignalType.RAPID_SELLOUT: [
        (_kw(r"\bsold\s+out\s+within\b"), 90),
        (_kw(r"\bsold\s+out\s+in\s+minutes\b"), 90),
        (_kw(r"\bsold\s+out\s+immediately\b"), 85),
        (_kw(r"\bsold\s+out\s+fast\b"), 75),
        (_kw(r"\bsold\s+quickly\b"), 65),
    ],
    SignalType.HIGH_DEMAND: [
        (_kw(r"\bhigh\s+demand\b"), 70),
        (_kw(r"\bin\s+high\s+demand\b"), 70),
        (_kw(r"\bhighly\s+sought[\s-]after\b"), 70),
        (_kw(r"\bflying\s+off\s+the\s+shelves\b"), 75),
    ],
    SignalType.RISING_DEMAND: [
        (_kw(r"\bdemand\s+is\s+rising\b"), 70),
        (_kw(r"\brising\s+demand\b"), 70),
        (_kw(r"\bgrowing\s+interest\b"), 60),
    ],
    SignalType.SURGING_DEMAND: [
        (_kw(r"\bdemand\s+is\s+surging\b"), 80),
        (_kw(r"\bsurging\s+demand\b"), 80),
        (_kw(r"\brapid(?:ly)?\s+(?:growing|rising)\s+demand\b"), 75),
    ],
    SignalType.COMMUNITY_HYPE: [
        (_kw(r"\bcollectors?\s+(?:are|is)\s+excited\b"), 70),
        (_kw(r"\bcommunity\s+(?:demand|buzz|hype)\b"), 70),
        (_kw(r"\bhype\b"), 55),
        (_kw(r"\bbuzz\b"), 50),
    ],
    SignalType.SEALED_PRODUCT: [
        (_kw(r"\bfactory\s+sealed\b"), 80),
        (_kw(r"\bstill\s+sealed\b"), 75),
        (_kw(r"\bsealed\s+product\b"), 75),
        (_kw(r"\bunopened\b"), 60),
    ],
}


# ---------------------------------------------------------------
# Confidence weighting inputs
# ---------------------------------------------------------------

SOURCE_TYPE_CONFIDENCE_ADJUSTMENT = {
    SourceType.OFFICIAL.value: 10,
    SourceType.RETAILER.value: 10,
    SourceType.PRESS_RELEASE.value: 5,
    SourceType.EVENT.value: 5,
    SourceType.NEWS.value: 0,
    SourceType.MARKETPLACE.value: 0,
    SourceType.COMMUNITY.value: -10,
    SourceType.SOCIAL.value: -15,
    SourceType.OTHER.value: -5,
}

CERTAINTY_ADJUSTMENT = {
    "confirmed": 0,
    "estimated": -15,
    "rumored": -35,
}


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))


def _resolve_source_type(source):
    if not source.source_type:
        return None

    value = source.source_type

    return (
        value.value
        if hasattr(value, "value")
        else str(value).upper()
    )


def _adjusted_confidence(
    base_confidence, source, certainty
):
    source_type = _resolve_source_type(source)

    adjustment = (
        SOURCE_TYPE_CONFIDENCE_ADJUSTMENT.get(
            source_type, 0
        )
        + CERTAINTY_ADJUSTMENT.get(certainty, 0)
    )

    return _clamp(base_confidence + adjustment)


# ---------------------------------------------------------------
# Keyword-based detection
# ---------------------------------------------------------------

def _detect_keyword_signals(text, source):
    detections = []

    for signal_type, patterns in (
        KEYWORD_SIGNALS.items()
    ):
        matched_any = False

        for pattern, base_confidence in patterns:
            for match in pattern.finditer(text):
                if is_locally_negated(
                    text, match.start()
                ):
                    continue

                certainty = classify_certainty(
                    text, match.start()
                )

                detections.append(
                    SignalDetection(
                        signal_type=(
                            signal_type.value
                        ),
                        confidence=(
                            _adjusted_confidence(
                                base_confidence,
                                source,
                                certainty,
                            )
                        ),
                        evidence_text=(
                            match.group(0)
                        ),
                        evidence_start=(
                            match.start()
                        ),
                        evidence_end=match.end(),
                        source_field="body",
                        **certainty_flags(
                            certainty
                        ),
                    )
                )

                matched_any = True
                break

            if matched_any:
                break

    return detections


# ---------------------------------------------------------------
# Numeric / structured detections
# ---------------------------------------------------------------

def _detect_price_signals(text, source):
    detections = []

    for amount in find_currency_amounts(text):
        context = classify_price_context(
            text, amount["start"], amount["end"]
        )

        certainty = classify_certainty(
            text, amount["start"]
        )

        if context == "spend":
            signal_type = (
                SignalType.SPEND_REQUIREMENT
            )
            base_confidence = 85

        elif context == "resale":
            signal_type = (
                SignalType.OBSERVED_RESALE_PRICE
            )
            base_confidence = 75

        elif context == "retail":
            signal_type = SignalType.RETAIL_PRICE
            base_confidence = 75

        else:
            # A bare number with no classifying context is too
            # ambiguous to assert a role for - skip rather than
            # guess which figure it represents.
            continue

        notes = None

        if signal_type == (
            SignalType.OBSERVED_RESALE_PRICE
        ) and mentions_complete_set(
            text, amount["start"], amount["end"]
        ):
            notes = (
                "This figure appears to describe "
                "a complete set, not a single item."
            )

        detections.append(
            SignalDetection(
                signal_type=signal_type.value,
                confidence=_adjusted_confidence(
                    base_confidence,
                    source,
                    certainty,
                ),
                evidence_text=amount[
                    "matched_text"
                ],
                evidence_start=amount["start"],
                evidence_end=amount["end"],
                extracted_value=amount["amount"],
                extracted_unit=amount["currency"],
                source_field="body",
                notes=notes,
                **certainty_flags(certainty),
            )
        )

        if (
            signal_type
            == SignalType.OBSERVED_RESALE_PRICE
            and notes
        ):
            detections.append(
                SignalDetection(
                    signal_type=(
                        SignalType.RISK_WARNING.value
                    ),
                    confidence=70,
                    evidence_text=amount[
                        "matched_text"
                    ],
                    evidence_start=amount["start"],
                    evidence_end=amount["end"],
                    notes=notes,
                    source_field="body",
                    **certainty_flags(certainty),
                )
            )

    return detections


def _detect_quantity_signals(text, source):
    detections = []

    limited = find_limited_quantity(text)

    if limited:
        certainty = classify_certainty(
            text, limited["start"]
        )

        detections.append(
            SignalDetection(
                signal_type=(
                    SignalType.LIMITED_QUANTITY.value
                ),
                confidence=_adjusted_confidence(
                    80, source, certainty
                ),
                evidence_text=limited[
                    "matched_text"
                ],
                evidence_start=limited["start"],
                evidence_end=limited["end"],
                extracted_value=limited["value"],
                extracted_unit="units",
                source_field="body",
                **certainty_flags(certainty),
            )
        )

    purchase_limit = find_purchase_limit(text)

    if purchase_limit:
        certainty = classify_certainty(
            text, purchase_limit["start"]
        )

        detections.append(
            SignalDetection(
                signal_type=(
                    SignalType.PURCHASE_LIMIT.value
                ),
                confidence=_adjusted_confidence(
                    85, source, certainty
                ),
                evidence_text=purchase_limit[
                    "matched_text"
                ],
                evidence_start=(
                    purchase_limit["start"]
                ),
                evidence_end=purchase_limit["end"],
                extracted_value=(
                    purchase_limit["value"]
                ),
                extracted_unit=(
                    "per customer"
                ),
                source_field="body",
                **certainty_flags(certainty),
            )
        )

    numbered = find_numbered_release(text)

    if numbered:
        certainty = classify_certainty(
            text, numbered["start"]
        )

        detections.append(
            SignalDetection(
                signal_type=(
                    SignalType.NUMBERED_RELEASE.value
                ),
                confidence=_adjusted_confidence(
                    75, source, certainty
                ),
                evidence_text=numbered[
                    "matched_text"
                ],
                evidence_start=numbered["start"],
                evidence_end=numbered["end"],
                source_field="body",
                **certainty_flags(certainty),
            )
        )

    return detections


def _detect_release_window_signals(
    text, source
):
    detections = []

    window = find_purchase_window(text)

    if window:
        certainty = classify_certainty(
            text, window["start"]
        )

        detections.append(
            SignalDetection(
                signal_type=(
                    SignalType.PURCHASE_WINDOW.value
                ),
                confidence=_adjusted_confidence(
                    75, source, certainty
                ),
                evidence_text=window[
                    "matched_text"
                ],
                evidence_start=window["start"],
                evidence_end=window["end"],
                extracted_value={
                    "start": window[
                        "window_start"
                    ],
                    "end": window["window_end"],
                },
                source_field="body",
                **certainty_flags(certainty),
            )
        )

    else:
        dates = find_dates(text)

        if dates:
            first_date = dates[0]
            certainty = classify_certainty(
                text, first_date["start"]
            )

            detections.append(
                SignalDetection(
                    signal_type=(
                        SignalType.RELEASE_DATE.value
                    ),
                    confidence=(
                        _adjusted_confidence(
                            70, source, certainty
                        )
                    ),
                    evidence_text=first_date[
                        "matched_text"
                    ],
                    evidence_start=(
                        first_date["start"]
                    ),
                    evidence_end=first_date["end"],
                    source_field="body",
                    **certainty_flags(certainty),
                )
            )

    release_time = find_release_time(text)

    if release_time:
        certainty = classify_certainty(
            text, release_time["start"]
        )

        detections.append(
            SignalDetection(
                signal_type=(
                    SignalType.RELEASE_TIME.value
                ),
                confidence=_adjusted_confidence(
                    65, source, certainty
                ),
                evidence_text=release_time[
                    "matched_text"
                ],
                evidence_start=(
                    release_time["start"]
                ),
                evidence_end=release_time["end"],
                source_field="body",
                **certainty_flags(certainty),
            )
        )

    duration = find_sellout_duration(text)

    if duration:
        certainty = classify_certainty(
            text, duration["start"]
        )

        detections.append(
            SignalDetection(
                signal_type=(
                    SignalType.RAPID_SELLOUT.value
                ),
                confidence=_adjusted_confidence(
                    90, source, certainty
                ),
                evidence_text=duration[
                    "matched_text"
                ],
                evidence_start=duration["start"],
                evidence_end=duration["end"],
                extracted_value=duration["value"],
                extracted_unit=duration["unit"],
                source_field="body",
                notes=(
                    "Sold out duration extracted "
                    "from surrounding sellout "
                    "language."
                ),
                **certainty_flags(certainty),
            )
        )

    return detections


def _detect_collaboration_signals(
    text, source, entities
):
    detections = []

    collaboration = find_collaboration(text)

    if collaboration and (
        collaboration["right"]
        or has_collaboration_keyword(text)
    ):
        certainty = classify_certainty(
            text, collaboration["start"]
        )

        detections.append(
            SignalDetection(
                signal_type=(
                    SignalType.COLLABORATION.value
                ),
                confidence=_adjusted_confidence(
                    80, source, certainty
                ),
                evidence_text=collaboration[
                    "matched_text"
                ],
                evidence_start=(
                    collaboration["start"]
                ),
                evidence_end=collaboration["end"],
                extracted_value={
                    "left": collaboration["left"],
                    "right": collaboration[
                        "right"
                    ],
                },
                source_field="body",
                **certainty_flags(certainty),
            )
        )

        if collaboration["left"]:
            entities.franchise = (
                entities.franchise
                or collaboration["left"]
            )
            entities.brand = (
                entities.brand
                or collaboration["left"]
            )

        entities.collaboration_partner = (
            entities.collaboration_partner
            or collaboration["right"]
        )

    return detections


def _detect_pack_quantity_note(
    text, detections
):
    pack_quantity = find_pack_quantity(text)

    if not pack_quantity:
        return

    for detection in detections:
        if (
            detection.signal_type
            == SignalType.PROMOTIONAL_PACK.value
        ):
            detection.extracted_value = (
                pack_quantity["value"]
            )
            detection.extracted_unit = "packs"
            return


def _derive_high_acquisition_difficulty(
    detections, source
):
    barrier_types = {
        SignalType.LOTTERY_REQUIRED.value,
        SignalType.MEMBERSHIP_EXCLUSIVE.value,
        SignalType.EVENT_ATTENDANCE_REQUIRED.value,
        SignalType.BUNDLE_REQUIRED.value,
        SignalType.RETAILER_EXCLUSIVE.value,
        SignalType.EVENT_EXCLUSIVE.value,
        SignalType.SPEND_REQUIREMENT.value,
    }

    contributing = [
        detection
        for detection in detections
        if detection.signal_type in barrier_types
        and not detection.rumored
    ]

    contributing_types = {
        detection.signal_type
        for detection in contributing
    }

    if len(contributing_types) < 2:
        return None

    average_confidence = sum(
        detection.confidence
        for detection in contributing
    ) / len(contributing)

    return SignalDetection(
        signal_type=(
            SignalType.HIGH_ACQUISITION_DIFFICULTY.value
        ),
        confidence=_clamp(average_confidence),
        evidence_text=", ".join(
            sorted(contributing_types)
        ),
        confirmed=True,
        notes=(
            "Derived from multiple acquisition "
            "barriers detected together: "
            + ", ".join(sorted(contributing_types))
        ),
    )


def _detect_rumor_signal(text, source):
    from collector_intelligence.extraction import (
        RUMOR_MARKERS,
    )

    lowered = text.lower()
    found = [
        marker
        for marker in RUMOR_MARKERS
        if marker in lowered
    ]

    if not found:
        return None

    position = lowered.find(found[0])

    return SignalDetection(
        signal_type=SignalType.RUMOR.value,
        confidence=_adjusted_confidence(
            60, source, "rumored"
        ),
        evidence_text=found[0],
        evidence_start=position,
        evidence_end=position + len(found[0]),
        rumored=True,
        source_field="body",
        notes=(
            "Rumor language detected - this "
            "report is not a confirmed release."
        ),
    )


# ---------------------------------------------------------------
# Relevance scoring + should_create_opportunity
# ---------------------------------------------------------------

RELEVANCE_WEIGHTS = {
    SignalType.COLLABORATION.value: 20,
    SignalType.FIRST_COLLABORATION.value: 10,
    SignalType.EXCLUSIVE_PROMO.value: 12,
    SignalType.PROMOTIONAL_PACK.value: 6,
    SignalType.ANNIVERSARY.value: 8,
    SignalType.FIRST_EDITION.value: 6,
    SignalType.EXCLUSIVE_ARTWORK.value: 5,
    SignalType.EXCLUSIVE_CHARACTER.value: 5,
    SignalType.EVENT_EXCLUSIVE.value: 8,
    SignalType.CONVENTION_EXCLUSIVE.value: 8,
    SignalType.TOURNAMENT_EXCLUSIVE.value: 8,
    SignalType.RETAILER_EXCLUSIVE.value: 7,
    SignalType.REGION_EXCLUSIVE.value: 6,
    SignalType.MEMBERSHIP_EXCLUSIVE.value: 8,
    SignalType.LOTTERY_REQUIRED.value: 8,
    SignalType.EVENT_ATTENDANCE_REQUIRED.value: 5,
    SignalType.BUNDLE_REQUIRED.value: 4,
    SignalType.REDEEMABLE_REWARD.value: 4,
    SignalType.LIMITED_QUANTITY.value: 10,
    SignalType.NUMBERED_RELEASE.value: 6,
    SignalType.SPEND_REQUIREMENT.value: 6,
    SignalType.OBSERVED_RESALE_PRICE.value: 12,
    SignalType.STATUS_SOLD_OUT.value: 4,
    SignalType.STATUS_RESTOCKED.value: 2,
    SignalType.LOW_STOCK.value: 4,
    SignalType.RAPID_SELLOUT.value: 12,
    SignalType.HIGH_DEMAND.value: 6,
    SignalType.RISING_DEMAND.value: 6,
    SignalType.SURGING_DEMAND.value: 10,
    SignalType.HIGH_ACQUISITION_DIFFICULTY.value: 8,
    SignalType.SEALED_PRODUCT.value: 3,
    SignalType.COMMUNITY_HYPE.value: 4,
    # Deliberately unweighted / neutral: a plain retail price or a
    # basic purchase limit is far too common on ordinary commerce
    # pages to be evidence of collector relevance by itself.
    SignalType.RETAIL_PRICE.value: 0,
    SignalType.PURCHASE_LIMIT.value: 0,
    SignalType.PURCHASE_WINDOW.value: 2,
    SignalType.RELEASE_DATE.value: 0,
    SignalType.RELEASE_TIME.value: 0,
    SignalType.STATUS_LIVE.value: 0,
    SignalType.RUMOR.value: 0,
    SignalType.RISK_WARNING.value: 0,
}


def _compute_relevance_score(detections):
    contribution_by_type = {}

    for detection in detections:
        weight = RELEVANCE_WEIGHTS.get(
            detection.signal_type, 0
        )

        if weight <= 0:
            continue

        weighted = weight * (
            detection.confidence / 100
        )

        contribution_by_type[
            detection.signal_type
        ] = max(
            contribution_by_type.get(
                detection.signal_type, 0
            ),
            weighted,
        )

    return _clamp(
        sum(contribution_by_type.values())
    )


def _compute_overall_confidence(detections):
    if not detections:
        return 0.0

    relevant = [
        detection
        for detection in detections
        if RELEVANCE_WEIGHTS.get(
            detection.signal_type, 0
        )
        > 0
    ]

    pool = relevant or detections

    return round(
        sum(
            detection.confidence
            for detection in pool
        )
        / len(pool),
        2,
    )


def _resale_materially_above_spend(
    detections
):
    resale = next(
        (
            detection
            for detection in detections
            if detection.signal_type
            == (
                SignalType.OBSERVED_RESALE_PRICE.value
            )
        ),
        None,
    )

    spend = next(
        (
            detection
            for detection in detections
            if detection.signal_type
            in {
                SignalType.SPEND_REQUIREMENT.value,
                SignalType.RETAIL_PRICE.value,
            }
        ),
        None,
    )

    if not resale or not spend:
        return False

    if not resale.extracted_value or not (
        spend.extracted_value
    ):
        return False

    return (
        resale.extracted_value
        >= spend.extracted_value * 1.5
    )


def _decide_should_create_opportunity(
    detections,
    entities,
    relevance_score,
    threshold,
):
    if not entities.has_any_identity():
        return (
            False,
            "missing_product_identity",
        )

    present_types = {
        detection.signal_type
        for detection in detections
    }

    strong_combo_rules = [
        (
            {
                SignalType.COLLABORATION.value,
            },
            present_types
            & {
                SignalType.EXCLUSIVE_PROMO.value,
                SignalType.EVENT_EXCLUSIVE.value,
                SignalType.RETAILER_EXCLUSIVE.value,
            },
        ),
        (
            {
                SignalType.SPEND_REQUIREMENT.value,
            },
            present_types
            & {
                SignalType.EXCLUSIVE_PROMO.value,
                SignalType.PROMOTIONAL_PACK.value,
            },
        ),
        (
            {
                SignalType.LIMITED_QUANTITY.value,
            },
            present_types
            & {
                SignalType.COLLABORATION.value,
                SignalType.EXCLUSIVE_PROMO.value,
                SignalType.ANNIVERSARY.value,
            },
        ),
        (
            {
                SignalType.ANNIVERSARY.value,
            },
            present_types
            & {
                SignalType.EXCLUSIVE_PROMO.value,
                SignalType.LIMITED_QUANTITY.value,
                SignalType.NUMBERED_RELEASE.value,
            },
        ),
        (
            {
                SignalType.STATUS_SOLD_OUT.value,
            },
            present_types
            & {
                SignalType.RISING_DEMAND.value,
                SignalType.SURGING_DEMAND.value,
                SignalType.HIGH_DEMAND.value,
                SignalType.RAPID_SELLOUT.value,
            },
        ),
    ]

    has_strong_combo = any(
        required.issubset(present_types)
        and bool(also_present)
        for required, also_present in (
            strong_combo_rules
        )
    )

    standalone_qualifiers = (
        {
            SignalType.EVENT_EXCLUSIVE.value,
            SignalType.CONVENTION_EXCLUSIVE.value,
            SignalType.TOURNAMENT_EXCLUSIVE.value,
            SignalType.LOTTERY_REQUIRED.value,
            SignalType.MEMBERSHIP_EXCLUSIVE.value,
            SignalType.RETAILER_EXCLUSIVE.value,
        }
        & present_types
    )

    if _resale_materially_above_spend(
        detections
    ):
        has_strong_combo = True

    if relevance_score < threshold:
        if has_strong_combo or (
            standalone_qualifiers
            and relevance_score
            >= threshold * 0.6
        ):
            pass
        else:
            return (
                False,
                (
                    "collector_relevance_score "
                    f"{relevance_score:.0f} is "
                    f"below the threshold of "
                    f"{threshold}"
                ),
            )

    only_weak_signals = present_types <= {
        SignalType.RUMOR.value,
        SignalType.RETAIL_PRICE.value,
        SignalType.STATUS_LIVE.value,
        SignalType.STATUS_RESTOCKED.value,
        SignalType.PURCHASE_LIMIT.value,
    }

    if only_weak_signals:
        return (
            False,
            (
                "only weak/common signals were "
                "detected (e.g. an ordinary "
                "restock or price mention)"
            ),
        )

    return True, None


# ---------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------

def _extract_entities(text, source, detections):
    entities = ExtractedEntities()

    if source.brand_hint:
        entities.brand = source.brand_hint

    if source.franchise_hint:
        entities.franchise = source.franchise_hint

    if source.retailer:
        entities.retailer = source.retailer

    return entities


# ---------------------------------------------------------------
# Missing critical fields / warnings
# ---------------------------------------------------------------

def _compute_missing_and_warnings(
    detections, entities, source
):
    missing = []
    warnings = []

    if not entities.has_any_identity():
        missing.append("product_identity")

    price_types = {
        SignalType.SPEND_REQUIREMENT.value,
        SignalType.RETAIL_PRICE.value,
        SignalType.OBSERVED_RESALE_PRICE.value,
    }

    present_types = {
        detection.signal_type
        for detection in detections
    }

    if not (present_types & price_types):
        missing.append("pricing_information")

    status_types = {
        SignalType.STATUS_LIVE.value,
        SignalType.STATUS_SOLD_OUT.value,
        SignalType.STATUS_RESTOCKED.value,
        SignalType.RELEASE_DATE.value,
        SignalType.PURCHASE_WINDOW.value,
    }

    if not (present_types & status_types):
        missing.append(
            "release_or_availability_status"
        )

    conflicting_status_pairs = [
        (
            SignalType.STATUS_SOLD_OUT.value,
            SignalType.STATUS_LIVE.value,
        ),
        (
            SignalType.STATUS_SOLD_OUT.value,
            SignalType.STATUS_RESTOCKED.value,
        ),
    ]

    for left, right in (
        conflicting_status_pairs
    ):
        if left in present_types and (
            right in present_types
        ):
            warnings.append(
                "Conflicting availability "
                f"signals detected ({left} and "
                f"{right}) - review source text "
                "manually."
            )

    if not entities.has_any_identity() and (
        SignalType.RUMOR.value in present_types
    ):
        warnings.append(
            "Rumor language detected with no "
            "identifiable product - insufficient "
            "information to generate a reliable "
            "deduplication key."
        )

    return missing, warnings


# ---------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------

def detect_signals(
    source, threshold=DEFAULT_RELEVANCE_THRESHOLD
):
    """
    Runs every deterministic detector against `source` (a
    RawSourceInput) and returns a SignalDetectionResult. Never
    raises for ordinary/malformed-looking input; never fabricates a
    value that isn't backed by matched text.
    """
    text = source.full_text

    entities = _extract_entities(
        text, source, []
    )

    detections = []
    detections.extend(
        _detect_keyword_signals(text, source)
    )
    detections.extend(
        _detect_price_signals(text, source)
    )
    detections.extend(
        _detect_quantity_signals(text, source)
    )
    detections.extend(
        _detect_release_window_signals(
            text, source
        )
    )
    detections.extend(
        _detect_collaboration_signals(
            text, source, entities
        )
    )

    _detect_pack_quantity_note(
        text, detections
    )

    rumor_signal = _detect_rumor_signal(
        text, source
    )

    if rumor_signal:
        detections.append(rumor_signal)

    derived = (
        _derive_high_acquisition_difficulty(
            detections, source
        )
    )

    if derived:
        detections.append(derived)

    relevance_score = _compute_relevance_score(
        detections
    )

    overall_confidence = (
        _compute_overall_confidence(detections)
    )

    should_create, rejection_reason = (
        _decide_should_create_opportunity(
            detections,
            entities,
            relevance_score,
            threshold,
        )
    )

    missing, warnings = (
        _compute_missing_and_warnings(
            detections, entities, source
        )
    )

    return SignalDetectionResult(
        raw_source=source,
        detected_signals=detections,
        extracted_entities=entities,
        warnings=warnings,
        missing_critical_fields=missing,
        overall_signal_confidence=(
            overall_confidence
        ),
        collector_relevance_score=(
            relevance_score
        ),
        should_create_opportunity=should_create,
        rejection_reason=rejection_reason,
    )
