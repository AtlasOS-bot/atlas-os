from scouts.tcg.profiles import (
    get_tcg_profile,
    normalize_tcg_name,
)


def calculate_tcg_intelligence(
    item,
    tcg_name,
):
    normalized_tcg = normalize_tcg_name(
        tcg_name
    )

    profile = get_tcg_profile(
        normalized_tcg
    )

    title = clean_text(
        item.get("title")
    )

    description = clean_text(
        item.get("description")
    )

    searchable_text = (
        f"{title} {description}"
    ).lower()

    product_type = item.get(
        "product_type",
        "other",
    )

    collector_score = profile[
        "base_scores"
    ].get(
        product_type,
        5,
    )

    reasons = [
        (
            f"Base collector score for "
            f"{product_type}: "
            f"{collector_score} point(s)."
        )
    ]

    high_value_points = score_terms(
        text=searchable_text,
        weighted_terms=profile[
            "high_value_terms"
        ],
        reasons=reasons,
        reason_prefix=(
            "Collector-demand signal"
        ),
    )

    scarcity_points = score_terms(
        text=searchable_text,
        weighted_terms=profile[
            "scarcity_terms"
        ],
        reasons=reasons,
        reason_prefix=(
            "Scarcity signal"
        ),
    )

    risk_points = score_terms(
        text=searchable_text,
        weighted_terms=profile[
            "risk_terms"
        ],
        reasons=reasons,
        reason_prefix="Supply-risk signal",
    )

    collector_score += (
        high_value_points
        + scarcity_points
        + risk_points
    )

    if item.get("sealed_product"):
        collector_score += 8

        reasons.append(
            "Sealed-product status added "
            "8 collector point(s)."
        )

    if item.get("promo_included"):
        collector_score += 10

        reasons.append(
            "Included promotional content added "
            "10 collector point(s)."
        )

    if item.get("collector_variant"):
        collector_score += 10

        reasons.append(
            "A collector-oriented variant added "
            "10 collector point(s)."
        )

    if item.get("limited_release"):
        collector_score += 10

        reasons.append(
            "Limited-release language added "
            "10 collector point(s)."
        )

    collector_score = clamp_score(
        collector_score
    )

    popularity_score = calculate_popularity_score(
        item=item,
        high_value_points=(
            high_value_points
        ),
        scarcity_points=scarcity_points,
    )

    flip_score = calculate_flip_score(
        item=item,
        collector_score=collector_score,
        popularity_score=popularity_score,
    )

    hold_score = calculate_hold_score(
        item=item,
        collector_score=collector_score,
        scarcity_points=scarcity_points,
    )

    sleeper_score = calculate_sleeper_score(
        item=item,
        collector_score=collector_score,
        popularity_score=popularity_score,
    )

    strategy_scores = {
        "QUICK FLIP": flip_score,
        "LONG-TERM HOLD": hold_score,
        "SLEEPER WATCH": sleeper_score,
    }

    best_strategy_name = max(
        strategy_scores,
        key=strategy_scores.get,
    )

    best_strategy_score = (
        strategy_scores[
            best_strategy_name
        ]
    )

    return {
        "collector_score": (
            collector_score
        ),
        "collector_level": score_level(
            collector_score
        ),
        "popularity_score": (
            popularity_score
        ),
        "popularity_level": score_level(
            popularity_score
        ),
        "flip_score": flip_score,
        "flip_level": score_level(
            flip_score
        ),
        "hold_score": hold_score,
        "hold_level": score_level(
            hold_score
        ),
        "sleeper_score": (
            sleeper_score
        ),
        "sleeper_level": score_level(
            sleeper_score
        ),
        "best_strategy": {
            "strategy": (
                best_strategy_name
            ),
            "score": (
                best_strategy_score
            ),
            "reason": strategy_reason(
                best_strategy_name
            ),
        },
        "collector_reasons": reasons,
    }


def calculate_popularity_score(
    item,
    high_value_points,
    scarcity_points,
):
    score = 12

    sources = item.get(
        "sources",
        [],
    )

    if isinstance(sources, str):
        sources = [sources]

    source_count = len(
        set(sources)
    )

    if source_count >= 3:
        score += 24

    elif source_count == 2:
        score += 15

    elif source_count == 1:
        score += 6

    score += round(
        max(
            high_value_points,
            0,
        )
        * 0.60
    )

    score += round(
        max(
            scarcity_points,
            0,
        )
        * 0.35
    )

    if item.get("limited_release"):
        score += 8

    if item.get("promo_included"):
        score += 6

    return clamp_score(score)


def calculate_flip_score(
    item,
    collector_score,
    popularity_score,
):
    score = 10

    score += round(
        collector_score * 0.28
    )

    score += round(
        popularity_score * 0.42
    )

    if item.get("limited_release"):
        score += 10

    if item.get("promo_included"):
        score += 8

    availability = normalize_availability(
        item.get("availability")
    )

    if availability in {
        "soldout",
        "outofstock",
        "unavailable",
    }:
        score += 12

    return clamp_score(score)


def calculate_hold_score(
    item,
    collector_score,
    scarcity_points,
):
    score = 8

    score += round(
        collector_score * 0.52
    )

    score += round(
        max(
            scarcity_points,
            0,
        )
        * 0.45
    )

    if item.get("sealed_product"):
        score += 12

    if item.get("collector_variant"):
        score += 10

    if item.get("promo_included"):
        score += 8

    return clamp_score(score)


def calculate_sleeper_score(
    item,
    collector_score,
    popularity_score,
):
    score = 10

    score += round(
        collector_score * 0.38
    )

    if popularity_score <= 30:
        score += 22

    elif popularity_score <= 50:
        score += 13

    elif popularity_score >= 75:
        score -= 10

    if item.get("limited_release"):
        score += 9

    if item.get("promo_included"):
        score += 7

    return clamp_score(score)


def score_terms(
    text,
    weighted_terms,
    reasons,
    reason_prefix,
):
    total = 0

    for term, weight in (
        weighted_terms.items()
    ):
        if term not in text:
            continue

        total += weight

        reasons.append(
            f"{reason_prefix}: '{term}' "
            f"added {weight} point(s)."
        )

    return total


def strategy_reason(strategy):
    reasons = {
        "QUICK FLIP": (
            "Current demand and scarcity signals "
            "favor selling quickly."
        ),
        "LONG-TERM HOLD": (
            "Collector value, sealed status, or "
            "scarcity favor holding longer."
        ),
        "SLEEPER WATCH": (
            "Collector value may be stronger than "
            "the product's current attention."
        ),
    }

    return reasons[strategy]


def score_level(score):
    if score >= 85:
        return "ELITE"

    if score >= 70:
        return "VERY HIGH"

    if score >= 55:
        return "HIGH"

    if score >= 35:
        return "MEDIUM"

    return "LOW"


def clamp_score(value):
    return max(
        0,
        min(
            round(value),
            100,
        ),
    )


def normalize_availability(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )