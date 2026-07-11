PRODUCT_BASE_SCORES = {
    "booster_box": 34,
    "elite_trainer_box": 32,
    "booster_bundle": 27,
    "collection_box": 24,
    "single_card": 22,
    "tin": 16,
    "plush": 18,
    "figure": 16,
    "pin": 10,
    "accessory": 7,
    "other": 5,
}


def calculate_collector_intelligence(item):
    product_type = item.get(
        "product_type",
        "other",
    )

    score = PRODUCT_BASE_SCORES.get(
        product_type,
        5,
    )

    reasons = [
        (
            f"Base collector value for product type "
            f"'{product_type}': {score} points."
        )
    ]

    if item.get("pokemon_center_exclusive"):
        score += 22
        reasons.append(
            "Pokémon Center exclusivity adds substantial collector demand."
        )

    if item.get("promo_included"):
        score += 14
        reasons.append(
            "An included promo card increases collector appeal."
        )

    if item.get("limited_release"):
        score += 12
        reasons.append(
            "Limited-release language increases scarcity potential."
        )

    if item.get("sealed_product"):
        score += 8
        reasons.append(
            "Sealed Pokémon products generally retain collector appeal."
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
            "The product appears sold out or out of stock."
        )

    elif availability == "instock":
        score += 2
        reasons.append(
            "The item is currently available from an official source."
        )

    urgency = item.get(
        "release_urgency",
        {},
    )

    urgency_score = urgency.get(
        "score",
        0,
    )

    if urgency_score >= 90:
        score += 10
        reasons.append(
            "Release urgency is very high."
        )

    elif urgency_score >= 70:
        score += 7
        reasons.append(
            "Release urgency is high."
        )

    elif urgency_score >= 45:
        score += 3
        reasons.append(
            "Release urgency is moderate."
        )

    score = max(
        0,
        min(round(score), 100),
    )

    return {
        "score": score,
        "level": collector_level(score),
        "hold_profile": hold_profile(
            product_type=product_type,
            score=score,
        ),
        "reasons": reasons,
    }


def collector_level(score):
    if score >= 85:
        return "ELITE"

    if score >= 70:
        return "VERY HIGH"

    if score >= 55:
        return "HIGH"

    if score >= 35:
        return "MEDIUM"

    return "LOW"


def hold_profile(
    product_type,
    score,
):
    if score >= 85:
        return "STRONG LONG-TERM HOLD"

    if product_type in {
        "booster_box",
        "elite_trainer_box",
    } and score >= 65:
        return "LONG-TERM HOLD"

    if score >= 55:
        return "SHORT-TO-MEDIUM HOLD"

    if score >= 35:
        return "QUICK FLIP OR WATCH"

    return "LOW PRIORITY"