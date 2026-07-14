from datetime import (
    datetime,
    timezone,
)


CATEGORY_NAMES = {
    "pokemon": "Pokémon",
    "lorcana": "Disney Lorcana",
    "one_piece": "One Piece",
}


class TcgMoneyBoard:

    @staticmethod
    def build(items):
        ranked_items = []

        for item in items:
            ranked_item = (
                TcgMoneyBoard.analyze_item(
                    item
                )
            )

            ranked_items.append(
                ranked_item
            )

        ranked_items.sort(
            key=lambda item: (
                item.get(
                    "opportunity_score",
                    0,
                ),
                item.get(
                    "collector_score",
                    0,
                ),
                item.get(
                    "hold_score",
                    0,
                ),
                item.get(
                    "flip_score",
                    0,
                ),
            ),
            reverse=True,
        )

        for position, item in enumerate(
            ranked_items,
            start=1,
        ):
            item["overall_rank"] = (
                position
            )

        return {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "count": len(
                ranked_items
            ),
            "critical_count": count_tier(
                ranked_items,
                "CRITICAL",
            ),
            "high_count": count_tier(
                ranked_items,
                "HIGH",
            ),
            "medium_count": count_tier(
                ranked_items,
                "MEDIUM",
            ),
            "watch_count": count_tier(
                ranked_items,
                "WATCH",
            ),
            "items": ranked_items,
            "top_overall": (
                ranked_items[:20]
            ),
            "top_flips": rank_by_score(
                ranked_items,
                "flip_score",
            )[:10],
            "top_holds": rank_by_score(
                ranked_items,
                "hold_score",
            )[:10],
            "top_sleepers": rank_by_score(
                ranked_items,
                "sleeper_score",
            )[:10],
            "by_category": group_categories(
                ranked_items
            ),
        }

    @staticmethod
    def analyze_item(item):
        analyzed = dict(item)

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

        sleeper_score = number_value(
            item.get(
                "sleeper_score"
            )
        )

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
            strategy_score = number_value(
                strategy.get("score")
            )

            strategy_name = (
                strategy.get(
                    "strategy"
                )
                or "UNKNOWN"
            )

        else:
            strategy_score = 0
            strategy_name = str(
                strategy
            )

        base_score = (
            strategy_score * 0.30
            + collector_score * 0.22
            + hold_score * 0.16
            + flip_score * 0.16
            + popularity_score * 0.10
            + sleeper_score * 0.06
        )

        bonuses = []
        bonus_score = 0

        if item.get(
            "limited_release"
        ):
            bonus_score += 5

            bonuses.append(
                "Limited release"
            )

        if item.get(
            "promo_included"
        ):
            bonus_score += 4

            bonuses.append(
                "Promo included"
            )

        if item.get(
            "collector_variant"
        ):
            bonus_score += 4

            bonuses.append(
                "Collector variant"
            )

        if item.get(
            "sealed_product"
        ):
            bonus_score += 3

            bonuses.append(
                "Sealed product"
            )

        availability = (
            normalize_availability(
                item.get(
                    "availability"
                )
            )
        )

        if availability in {
            "soldout",
            "outofstock",
            "unavailable",
        }:
            bonus_score += 4

            bonuses.append(
                "Scarce availability"
            )

        opportunity_score = clamp_score(
            base_score + bonus_score
        )

        category = (
            str(
                item.get(
                    "category",
                    item.get(
                        "tcg_name",
                        "unknown",
                    ),
                )
            )
            .strip()
            .lower()
        )

        analyzed[
            "opportunity_score"
        ] = opportunity_score

        analyzed[
            "opportunity_tier"
        ] = opportunity_tier(
            opportunity_score
        )

        analyzed[
            "recommended_action"
        ] = recommended_action(
            score=opportunity_score,
            strategy=strategy_name,
        )

        analyzed[
            "game_name"
        ] = CATEGORY_NAMES.get(
            category,
            category.replace(
                "_",
                " ",
            ).title(),
        )

        analyzed[
            "money_board_reasons"
        ] = build_reasons(
            opportunity_score=(
                opportunity_score
            ),
            strategy=strategy_name,
            bonuses=bonuses,
            item=item,
        )

        return analyzed


def opportunity_tier(score):
    if score >= 85:
        return "CRITICAL"

    if score >= 70:
        return "HIGH"

    if score >= 55:
        return "MEDIUM"

    return "WATCH"


def recommended_action(
    score,
    strategy,
):
    if score >= 85:
        if strategy == "QUICK FLIP":
            return (
                "BUY QUICKLY IF MARGIN "
                "IS CONFIRMED"
            )

        if strategy == (
            "LONG-TERM HOLD"
        ):
            return (
                "PRIORITIZE FOR HOLD"
            )

        return (
            "RESEARCH IMMEDIATELY"
        )

    if score >= 70:
        if strategy == "QUICK FLIP":
            return (
                "CHECK STOCK AND MARKET PRICE"
            )

        if strategy == (
            "LONG-TERM HOLD"
        ):
            return (
                "CONSIDER BUYING FOR HOLD"
            )

        return (
            "ADD TO HIGH-PRIORITY WATCHLIST"
        )

    if score >= 55:
        return (
            "MONITOR PRICE AND AVAILABILITY"
        )

    return (
        "LOW-PRIORITY WATCH"
    )


def build_reasons(
    opportunity_score,
    strategy,
    bonuses,
    item,
):
    reasons = [
        (
            f"Combined opportunity score: "
            f"{opportunity_score}/100."
        ),
        (
            f"Best detected strategy: "
            f"{strategy}."
        ),
    ]

    if bonuses:
        reasons.append(
            "Detected advantages: "
            + ", ".join(
                bonuses
            )
            + "."
        )

    collector_score = number_value(
        item.get(
            "collector_score"
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

    if collector_score >= 70:
        reasons.append(
            "Collector demand is strong."
        )

    if flip_score >= 70:
        reasons.append(
            "Quick-flip potential is strong."
        )

    if hold_score >= 70:
        reasons.append(
            "Long-term hold potential is strong."
        )

    return reasons


def rank_by_score(
    items,
    field,
):
    return sorted(
        items,
        key=lambda item: (
            number_value(
                item.get(field)
            ),
            number_value(
                item.get(
                    "opportunity_score"
                )
            ),
        ),
        reverse=True,
    )


def group_categories(items):
    groups = {}

    for item in items:
        category = (
            str(
                item.get(
                    "category",
                    item.get(
                        "tcg_name",
                        "unknown",
                    ),
                )
            )
            .strip()
            .lower()
        )

        groups.setdefault(
            category,
            [],
        ).append(item)

    for category in groups:
        groups[category] = (
            groups[category][:20]
        )

    return groups


def count_tier(
    items,
    tier,
):
    return sum(
        1
        for item in items
        if item.get(
            "opportunity_tier"
        )
        == tier
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