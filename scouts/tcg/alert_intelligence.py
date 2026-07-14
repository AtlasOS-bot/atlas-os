EVENT_BASE_SCORES = {
    "RESTOCK": 48,
    "PRICE_DROP": 42,
    "TIER_UPGRADE": 36,
    "STRATEGY_UPGRADE": 32,
    "SOLD_OUT": 30,
    "NEW_PRODUCT": 24,
    "NEW_CONFIRMATION": 16,
    "PRICE_INCREASE": 8,
}


def analyze_tcg_alert(
    item,
    change,
):
    event = change.get(
        "event",
        "UNKNOWN",
    )

    score = EVENT_BASE_SCORES.get(
        event,
        0,
    )

    reasons = [
        (
            f"Event '{event}' added "
            f"{score} base point(s)."
        )
    ]

    opportunity_score = number_value(
        item.get(
            "opportunity_score"
        )
    )

    collector_score = number_value(
        item.get(
            "collector_score"
        )
    )

    popularity_score = number_value(
        item.get(
            "popularity_score"
        )
    )

    flip_score = number_value(
        item.get(
            "flip_score"
        )
    )

    hold_score = number_value(
        item.get(
            "hold_score"
        )
    )

    opportunity_points = round(
        opportunity_score * 0.15
    )

    collector_points = round(
        collector_score * 0.08
    )

    popularity_points = round(
        popularity_score * 0.06
    )

    score += opportunity_points
    score += collector_points
    score += popularity_points

    if opportunity_points:
        reasons.append(
            "Opportunity strength added "
            f"{opportunity_points} point(s)."
        )

    if collector_points:
        reasons.append(
            "Collector demand added "
            f"{collector_points} point(s)."
        )

    if popularity_points:
        reasons.append(
            "Popularity added "
            f"{popularity_points} point(s)."
        )

    if (
        event == "RESTOCK"
        and flip_score >= 70
    ):
        score += 12

        reasons.append(
            "High flip potential makes "
            "this restock more urgent."
        )

    if (
        event == "PRICE_DROP"
        and hold_score >= 70
    ):
        score += 10

        reasons.append(
            "Strong hold potential makes "
            "this price drop more attractive."
        )

    if (
        event == "TIER_UPGRADE"
        and item.get(
            "opportunity_tier"
        )
        == "CRITICAL"
    ):
        score += 12

        reasons.append(
            "The product entered the "
            "CRITICAL opportunity tier."
        )

    score = clamp_score(
        score
    )

    return {
        "event": event,
        "score": score,
        "priority": priority(
            score
        ),
        "action": recommended_action(
            event=event,
            score=score,
            item=item,
        ),
        "should_alert": (
            score >= 30
        ),
        "reason": change.get(
            "reason"
        ),
        "reasons": reasons,
    }


def priority(score):
    if score >= 85:
        return "CRITICAL"

    if score >= 70:
        return "HIGH"

    if score >= 50:
        return "MEDIUM"

    if score >= 30:
        return "LOW"

    return "IGNORE"


def recommended_action(
    event,
    score,
    item,
):
    strategy = (
        item.get(
            "best_strategy"
        )
        or {}
    )

    if isinstance(
        strategy,
        dict,
    ):
        strategy_name = (
            strategy.get(
                "strategy",
                "UNKNOWN",
            )
        )

    else:
        strategy_name = str(
            strategy
        )

    if event == "RESTOCK":
        if score >= 70:
            return (
                "CHECK STOCK AND BUY "
                "QUICKLY IF MARGIN WORKS"
            )

        return (
            "CHECK CURRENT STOCK"
        )

    if event == "PRICE_DROP":
        if strategy_name == (
            "LONG-TERM HOLD"
        ):
            return (
                "REVIEW FOR HOLD PURCHASE"
            )

        return (
            "RECHECK PROFIT MARGIN"
        )

    if event == "NEW_PRODUCT":
        if score >= 70:
            return (
                "RESEARCH IMMEDIATELY"
            )

        return (
            "ADD TO WATCHLIST"
        )

    if event == "SOLD_OUT":
        return (
            "WATCH SECONDARY MARKET"
        )

    if event == "TIER_UPGRADE":
        return (
            "REVIEW BUY PRIORITY"
        )

    if event == (
        "STRATEGY_UPGRADE"
    ):
        return (
            "RECHECK INVESTMENT STRATEGY"
        )

    if event == (
        "NEW_CONFIRMATION"
    ):
        return (
            "REVIEW NEW OFFICIAL DATA"
        )

    if event == (
        "PRICE_INCREASE"
    ):
        return (
            "RECALCULATE PROFIT MARGIN"
        )

    return "MONITOR"


def number_value(value):
    try:
        return float(
            value or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def clamp_score(value):
    return max(
        0,
        min(
            round(value),
            100,
        ),
    )