EVENT_BASE_SCORES = {
    "RESTOCK": 45,
    "PRICE_DROP": 40,
    "SOLD_OUT": 32,
    "NEW_PRODUCT": 25,
    "NEW_CONFIRMATION": 18,
    "PRICE_INCREASE": 8,
    "NO_CHANGE": 0,
}


def calculate_alert_intelligence(item):
    state_change = item.get(
        "state_change",
        {},
    )

    event = state_change.get(
        "event",
        "NO_CHANGE",
    )

    score = EVENT_BASE_SCORES.get(
        event,
        0,
    )

    reasons = [
        (
            f"Product event '{event}' contributed "
            f"{score} alert point(s)."
        )
    ]

    popularity_score = item.get(
        "popularity_score",
        0,
    )

    collector_score = item.get(
        "collector_score",
        0,
    )

    flip_score = item.get(
        "flip_score",
        0,
    )

    hold_score = item.get(
        "hold_score",
        0,
    )

    sleeper_score = item.get(
        "sleeper_score",
        0,
    )

    consensus_score = item.get(
        "consensus_score",
        0,
    )

    popularity_points = round(
        popularity_score * 0.12
    )

    collector_points = round(
        collector_score * 0.10
    )

    consensus_points = round(
        consensus_score * 0.08
    )

    score += popularity_points
    score += collector_points
    score += consensus_points

    if popularity_points:
        reasons.append(
            f"Popularity added {popularity_points} point(s)."
        )

    if collector_points:
        reasons.append(
            f"Collector value added {collector_points} point(s)."
        )

    if consensus_points:
        reasons.append(
            f"Official-source consensus added "
            f"{consensus_points} point(s)."
        )

    if event in {
        "RESTOCK",
        "PRICE_DROP",
        "NEW_PRODUCT",
    }:
        strategy_score = max(
            flip_score,
            hold_score,
            sleeper_score,
        )

        strategy_points = round(
            strategy_score * 0.12
        )

        score += strategy_points

        if strategy_points:
            reasons.append(
                f"Investment strategy strength added "
                f"{strategy_points} point(s)."
            )

    if (
        event == "RESTOCK"
        and flip_score >= 70
    ):
        score += 10

        reasons.append(
            "A high flip score increases the importance "
            "of this restock."
        )

    if (
        event == "PRICE_DROP"
        and hold_score >= 70
    ):
        score += 10

        reasons.append(
            "A strong hold score makes this price drop "
            "more attractive."
        )

    score = clamp_score(score)

    return {
        "event": event,
        "score": score,
        "priority": alert_priority(score),
        "action": recommended_alert_action(
            event=event,
            score=score,
            item=item,
        ),
        "should_alert": should_alert(
            event=event,
            score=score,
        ),
        "reasons": reasons,
    }


def should_alert(event, score):
    if event == "NO_CHANGE":
        return False

    return score >= 30


def alert_priority(score):
    if score >= 85:
        return "CRITICAL"

    if score >= 70:
        return "HIGH"

    if score >= 50:
        return "MEDIUM"

    if score >= 30:
        return "LOW"

    return "IGNORE"


def recommended_alert_action(
    event,
    score,
    item,
):
    if event == "RESTOCK":
        if score >= 70:
            return "CHECK AND BUY QUICKLY"

        return "CHECK AVAILABILITY"

    if event == "PRICE_DROP":
        if item.get("hold_score", 0) >= 70:
            return "REVIEW FOR LONG-TERM HOLD"

        return "REVIEW NEW PRICE"

    if event == "SOLD_OUT":
        return "WATCH SECONDARY MARKET"

    if event == "NEW_PRODUCT":
        if score >= 70:
            return "RESEARCH IMMEDIATELY"

        return "ADD TO WATCHLIST"

    if event == "NEW_CONFIRMATION":
        return "RECHECK PRODUCT CONFIDENCE"

    if event == "PRICE_INCREASE":
        return "REVIEW MARGIN"

    return "NO ACTION"


def clamp_score(score):
    return max(
        0,
        min(round(score), 100),
    )