from datetime import date, datetime, timezone


HIGH_DEMAND_TERMS = {
    "pokemon center exclusive": 18,
    "pokémon center exclusive": 18,
    "elite trainer box": 15,
    "etb": 12,
    "booster box": 15,
    "booster bundle": 12,
    "premium collection": 12,
    "special collection": 10,
    "promo card": 12,
    "promo cards": 12,
    "anniversary": 12,
    "limited": 10,
    "exclusive": 10,
    "preorder": 8,
    "pre-order": 8,
}

MEDIUM_DEMAND_TERMS = {
    "plush": 7,
    "figure": 7,
    "collector": 7,
    "collection": 5,
    "tin": 5,
    "pin": 4,
    "booster pack": 5,
    "trading card game": 5,
    "tcg": 4,
}

NEGATIVE_TERMS = {
    "reprint": -15,
    "restock": -8,
    "available again": -8,
    "general release": -5,
}


def analyze_pokemon_popularity(item):
    text = (
        f"{item.get('title', '')} "
        f"{item.get('description', '')}"
    ).lower()

    score = 10
    signals = []
    reasons = []

    source_names = normalized_sources(item)
    source_count = len(source_names)

    if source_count >= 3:
        add_signal(
            signals=signals,
            reasons=reasons,
            name="multi_source_confirmation",
            weight=20,
            reason=(
                f"{source_count} independent sources confirmed "
                "or referenced this product."
            ),
        )
        score += 20

    elif source_count == 2:
        add_signal(
            signals=signals,
            reasons=reasons,
            name="multi_source_confirmation",
            weight=12,
            reason="Two independent sources referenced this product.",
        )
        score += 12

    elif source_count == 1:
        add_signal(
            signals=signals,
            reasons=reasons,
            name="single_source_confirmation",
            weight=4,
            reason="One source currently confirms this product.",
        )
        score += 4

    if contains_source(source_names, "pokemon_center"):
        add_signal(
            signals=signals,
            reasons=reasons,
            name="pokemon_center_source",
            weight=12,
            reason=(
                "Pokémon Center exposure can create rapid collector "
                "attention, especially for exclusives."
            ),
        )
        score += 12

    if contains_source(source_names, "pokemon_news"):
        add_signal(
            signals=signals,
            reasons=reasons,
            name="official_news_source",
            weight=8,
            reason="The product appeared in official Pokémon news.",
        )
        score += 8

    matched_terms = set()

    for term, weight in HIGH_DEMAND_TERMS.items():
        if term in text and term not in matched_terms:
            matched_terms.add(term)
            score += weight

            add_signal(
                signals=signals,
                reasons=reasons,
                name=f"high_demand:{term}",
                weight=weight,
                reason=f"High-demand Pokémon signal detected: {term}.",
            )

    for term, weight in MEDIUM_DEMAND_TERMS.items():
        if term in text and term not in matched_terms:
            matched_terms.add(term)
            score += weight

            add_signal(
                signals=signals,
                reasons=reasons,
                name=f"collector_interest:{term}",
                weight=weight,
                reason=f"Collector-interest signal detected: {term}.",
            )

    for term, weight in NEGATIVE_TERMS.items():
        if term in text:
            score += weight

            add_signal(
                signals=signals,
                reasons=reasons,
                name=f"supply_risk:{term}",
                weight=weight,
                reason=f"Supply-risk language detected: {term}.",
            )

    availability = (
        item.get("availability")
        or ""
    ).lower()

    if availability == "instock":
        score += 3

        add_signal(
            signals=signals,
            reasons=reasons,
            name="in_stock",
            weight=3,
            reason="The official structured data reports the item in stock.",
        )

    elif availability in {
        "soldout",
        "outofstock",
    }:
        score += 10

        add_signal(
            signals=signals,
            reasons=reasons,
            name="sold_out",
            weight=10,
            reason=(
                "Official structured data indicates limited or exhausted "
                "availability."
            ),
        )

    freshness_weight, freshness_reason = freshness_signal(
        item.get("release_date")
    )

    if freshness_weight:
        score += freshness_weight

        add_signal(
            signals=signals,
            reasons=reasons,
            name="release_freshness",
            weight=freshness_weight,
            reason=freshness_reason,
        )

    score = max(0, min(round(score), 100))

    return {
        "score": score,
        "level": popularity_level(score),
        "confidence": popularity_confidence(
            source_count=source_count,
            signal_count=len(signals),
        ),
        "source_count": source_count,
        "signals": signals,
        "reasons": reasons,
    }


def normalized_sources(item):
    values = []

    item_sources = item.get("sources")

    if isinstance(item_sources, list):
        values.extend(item_sources)

    elif isinstance(item_sources, str):
        values.append(item_sources)

    source = item.get("source")

    if source:
        values.append(source)

    source_url = item.get("source_url")

    if source_url:
        values.append(source_url)

    unique = []

    for value in values:
        normalized = str(value).strip().lower()

        if normalized and normalized not in unique:
            unique.append(normalized)

    return unique


def contains_source(sources, term):
    return any(
        term in source
        for source in sources
    )


def add_signal(
    signals,
    reasons,
    name,
    weight,
    reason,
):
    signals.append({
        "name": name,
        "weight": weight,
        "reason": reason,
    })

    reasons.append(reason)


def popularity_level(score):
    if score >= 85:
        return "VIRAL"

    if score >= 70:
        return "VERY HIGH"

    if score >= 55:
        return "HIGH"

    if score >= 35:
        return "MEDIUM"

    return "LOW"


def popularity_confidence(
    source_count,
    signal_count,
):
    if source_count >= 3 and signal_count >= 5:
        return "VERY HIGH"

    if source_count >= 2 and signal_count >= 3:
        return "HIGH"

    if source_count >= 1 and signal_count >= 2:
        return "MEDIUM"

    return "LOW"


def freshness_signal(value):
    parsed = parse_date(value)

    if parsed is None:
        return 0, ""

    today = datetime.now(
        timezone.utc
    ).date()

    age_days = (
        today - parsed
    ).days

    if age_days < 0:
        days_until_release = abs(age_days)

        if days_until_release <= 14:
            return (
                12,
                f"The release is scheduled within {days_until_release} day(s).",
            )

        if days_until_release <= 45:
            return (
                6,
                f"The release is scheduled within {days_until_release} day(s).",
            )

        return 0, ""

    if age_days <= 3:
        return (
            12,
            f"The release is very fresh at approximately {age_days} day(s) old.",
        )

    if age_days <= 14:
        return (
            7,
            f"The release is approximately {age_days} day(s) old.",
        )

    if age_days <= 30:
        return (
            3,
            f"The release is approximately {age_days} day(s) old.",
        )

    return 0, ""


def parse_date(value):
    if not value:
        return None

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    candidates = [
        text,
        text[:10],
    ]

    for candidate in candidates:
        try:
            return datetime.fromisoformat(
                candidate.replace(
                    "Z",
                    "+00:00",
                )
            ).date()

        except ValueError:
            continue

    return None