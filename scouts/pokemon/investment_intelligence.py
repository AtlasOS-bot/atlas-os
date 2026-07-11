FLIP_PRODUCT_BONUS = {
    "elite_trainer_box": 18,
    "booster_box": 16,
    "booster_bundle": 18,
    "collection_box": 14,
    "single_card": 18,
    "tin": 8,
    "plush": 10,
    "figure": 8,
    "pin": 4,
    "accessory": 2,
    "other": 0,
}


HOLD_PRODUCT_BONUS = {
    "booster_box": 24,
    "elite_trainer_box": 22,
    "booster_bundle": 14,
    "collection_box": 15,
    "single_card": 12,
    "tin": 10,
    "plush": 14,
    "figure": 12,
    "pin": 7,
    "accessory": 4,
    "other": 2,
}


SLEEPER_PRODUCT_BONUS = {
    "booster_box": 7,
    "elite_trainer_box": 5,
    "booster_bundle": 9,
    "collection_box": 16,
    "single_card": 14,
    "tin": 18,
    "plush": 18,
    "figure": 17,
    "pin": 15,
    "accessory": 10,
    "other": 8,
}


def calculate_investment_intelligence(item):
    product_type = item.get(
        "product_type",
        "other",
    )

    collector_score = item.get(
        "collector_score",
        0,
    )

    popularity = item.get(
        "popularity",
        {},
    )

    popularity_score = popularity.get(
        "score",
        item.get("popularity_score", 0),
    )

    release_urgency = item.get(
        "release_urgency",
        {},
    )

    urgency_score = release_urgency.get(
        "score",
        0,
    )

    flip_score, flip_reasons = calculate_flip_score(
        item=item,
        product_type=product_type,
        collector_score=collector_score,
        popularity_score=popularity_score,
        urgency_score=urgency_score,
    )

    hold_score, hold_reasons = calculate_hold_score(
        item=item,
        product_type=product_type,
        collector_score=collector_score,
        popularity_score=popularity_score,
    )

    sleeper_score, sleeper_reasons = calculate_sleeper_score(
        item=item,
        product_type=product_type,
        collector_score=collector_score,
        popularity_score=popularity_score,
        urgency_score=urgency_score,
    )

    best_strategy = choose_best_strategy(
        flip_score=flip_score,
        hold_score=hold_score,
        sleeper_score=sleeper_score,
    )

    return {
        "flip": {
            "score": flip_score,
            "level": investment_level(
                flip_score
            ),
            "reasons": flip_reasons,
        },
        "hold": {
            "score": hold_score,
            "level": investment_level(
                hold_score
            ),
            "reasons": hold_reasons,
        },
        "sleeper": {
            "score": sleeper_score,
            "level": investment_level(
                sleeper_score
            ),
            "reasons": sleeper_reasons,
        },
        "best_strategy": best_strategy,
    }


def calculate_flip_score(
    item,
    product_type,
    collector_score,
    popularity_score,
    urgency_score,
):
    score = FLIP_PRODUCT_BONUS.get(
        product_type,
        0,
    )

    reasons = [
        (
            f"Product-type quick-flip base: "
            f"{score} points."
        )
    ]

    popularity_points = round(
        popularity_score * 0.35
    )

    score += popularity_points

    if popularity_points:
        reasons.append(
            f"Popularity added {popularity_points} point(s)."
        )

    urgency_points = round(
        urgency_score * 0.25
    )

    score += urgency_points

    if urgency_points:
        reasons.append(
            f"Release urgency added {urgency_points} point(s)."
        )

    collector_points = round(
        collector_score * 0.15
    )

    score += collector_points

    if collector_points:
        reasons.append(
            f"Collector value added {collector_points} point(s)."
        )

    availability = (
        item.get("availability")
        or ""
    ).lower()

    if availability in {
        "soldout",
        "outofstock",
    }:
        score += 12
        reasons.append(
            "Sold-out availability increases immediate resale pressure."
        )

    if item.get(
        "pokemon_center_exclusive"
    ):
        score += 8
        reasons.append(
            "Pokémon Center exclusivity supports short-term demand."
        )

    return clamp_score(score), reasons


def calculate_hold_score(
    item,
    product_type,
    collector_score,
    popularity_score,
):
    score = HOLD_PRODUCT_BONUS.get(
        product_type,
        0,
    )

    reasons = [
        (
            f"Product-type long-term hold base: "
            f"{score} points."
        )
    ]

    collector_points = round(
        collector_score * 0.45
    )

    score += collector_points

    if collector_points:
        reasons.append(
            f"Collector value added {collector_points} point(s)."
        )

    popularity_points = round(
        popularity_score * 0.10
    )

    score += popularity_points

    if popularity_points:
        reasons.append(
            f"Popularity added {popularity_points} point(s)."
        )

    if item.get("sealed_product"):
        score += 10
        reasons.append(
            "Sealed status supports long-term collectibility."
        )

    if item.get(
        "pokemon_center_exclusive"
    ):
        score += 12
        reasons.append(
            "Pokémon Center exclusivity strengthens long-term scarcity."
        )

    if item.get("promo_included"):
        score += 8
        reasons.append(
            "An exclusive or included promo supports long-term appeal."
        )

    if item.get("limited_release"):
        score += 10
        reasons.append(
            "Limited-release language supports long-term scarcity."
        )

    return clamp_score(score), reasons


def calculate_sleeper_score(
    item,
    product_type,
    collector_score,
    popularity_score,
    urgency_score,
):
    score = SLEEPER_PRODUCT_BONUS.get(
        product_type,
        0,
    )

    reasons = [
        (
            f"Product-type sleeper base: "
            f"{score} points."
        )
    ]

    collector_points = round(
        collector_score * 0.35
    )

    score += collector_points

    if collector_points:
        reasons.append(
            f"Collector value added {collector_points} point(s)."
        )

    if popularity_score <= 35:
        score += 18
        reasons.append(
            "Low current popularity may indicate an overlooked product."
        )

    elif popularity_score <= 55:
        score += 10
        reasons.append(
            "Moderate attention may leave room for future appreciation."
        )

    else:
        score -= 8
        reasons.append(
            "High current popularity reduces sleeper potential."
        )

    if urgency_score <= 45:
        score += 8
        reasons.append(
            "Low urgency may allow the product to remain overlooked."
        )

    if item.get("limited_release"):
        score += 10
        reasons.append(
            "Limited availability can create delayed collector interest."
        )

    if item.get("promo_included"):
        score += 8
        reasons.append(
            "Included promo content may gain attention later."
        )

    return clamp_score(score), reasons


def choose_best_strategy(
    flip_score,
    hold_score,
    sleeper_score,
):
    scores = {
        "QUICK FLIP": flip_score,
        "LONG-TERM HOLD": hold_score,
        "SLEEPER WATCH": sleeper_score,
    }

    strategy = max(
        scores,
        key=scores.get,
    )

    return {
        "strategy": strategy,
        "score": scores[strategy],
        "reason": strategy_reason(
            strategy
        ),
    }


def strategy_reason(strategy):
    reasons = {
        "QUICK FLIP": (
            "Current demand and urgency favor selling quickly."
        ),
        "LONG-TERM HOLD": (
            "Collector value and scarcity favor a longer holding period."
        ),
        "SLEEPER WATCH": (
            "The product may be overlooked and worth monitoring."
        ),
    }

    return reasons[strategy]


def investment_level(score):
    if score >= 85:
        return "ELITE"

    if score >= 70:
        return "VERY HIGH"

    if score >= 55:
        return "HIGH"

    if score >= 35:
        return "MEDIUM"

    return "LOW"


def clamp_score(score):
    return max(
        0,
        min(round(score), 100),
    )