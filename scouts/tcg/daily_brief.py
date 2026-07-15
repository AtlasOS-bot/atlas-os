import re
from datetime import (
    datetime,
    timezone,
)


GAME_NAMES = {
    "pokemon": "Pokémon",
    "lorcana": "Disney Lorcana",
    "one_piece": "One Piece",
}


PRIORITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "WATCH": 0,
    "IGNORE": 0,
}


class TcgDailyBrief:

    @staticmethod
    def build(
        catalog_items,
        money_board,
        active_alerts,
        generated_at=None,
    ):
        generated_at = (
            generated_at
            or datetime.now(
                timezone.utc
            ).isoformat()
        )

        ranked_items = (
            money_board.get(
                "items",
                [],
            )
            or []
        )

        urgent_alerts = (
            rank_alerts(
                active_alerts
            )[:15]
        )

        top_overall = (
            ranked_items[:15]
        )

        top_flips = (
            money_board.get(
                "top_flips",
                [],
            )[:10]
        )

        top_holds = (
            money_board.get(
                "top_holds",
                [],
            )[:10]
        )

        top_sleepers = (
            money_board.get(
                "top_sleepers",
                [],
            )[:10]
        )

        category_leaders = (
            build_category_leaders(
                ranked_items
            )
        )

        data_quality = (
            calculate_data_quality(
                catalog_items
            )
        )

        action_queue = (
            build_action_queue(
                urgent_alerts=urgent_alerts,
                top_overall=top_overall,
            )
        )

        summary = {
            "generated_at": generated_at,
            "catalog_count": len(
                catalog_items
            ),
            "ranked_count": len(
                ranked_items
            ),
            "active_alert_count": len(
                active_alerts
            ),
            "critical_count": (
                money_board.get(
                    "critical_count",
                    0,
                )
            ),
            "high_count": (
                money_board.get(
                    "high_count",
                    0,
                )
            ),
            "medium_count": (
                money_board.get(
                    "medium_count",
                    0,
                )
            ),
            "watch_count": (
                money_board.get(
                    "watch_count",
                    0,
                )
            ),
        }

        return {
            "generated_at": generated_at,
            "summary": summary,
            "action_queue": action_queue,
            "urgent_alerts": urgent_alerts,
            "top_overall": top_overall,
            "top_flips": top_flips,
            "top_holds": top_holds,
            "top_sleepers": top_sleepers,
            "category_leaders": (
                category_leaders
            ),
            "data_quality": data_quality,
        }

    @staticmethod
    def render(
        brief,
        overall_limit=10,
        strategy_limit=5,
    ):
        summary = (
            brief.get(
                "summary",
                {},
            )
        )

        action_queue = (
            brief.get(
                "action_queue",
                [],
            )
        )

        urgent_alerts = (
            brief.get(
                "urgent_alerts",
                [],
            )
        )

        lines = [
            "=" * 72,
            "ATLAS CROSS-TCG DAILY COMMAND BRIEF",
            "=" * 72,
            (
                f"Generated: "
                f"{brief.get('generated_at', 'Unknown')}"
            ),
            (
                f"Catalog products: "
                f"{summary.get('catalog_count', 0)}"
            ),
            (
                f"Ranked products: "
                f"{summary.get('ranked_count', 0)}"
            ),
            (
                f"Active alerts: "
                f"{summary.get('active_alert_count', 0)}"
            ),
            (
                "Opportunity tiers: "
                f"{summary.get('critical_count', 0)} Critical | "
                f"{summary.get('high_count', 0)} High | "
                f"{summary.get('medium_count', 0)} Medium | "
                f"{summary.get('watch_count', 0)} Watch"
            ),
            "",
            "=" * 72,
            "TODAY'S ACTION QUEUE",
            "=" * 72,
        ]

        if not action_queue:
            lines.append(
                "No immediate TCG actions."
            )

        for position, action in enumerate(
            action_queue,
            start=1,
        ):
            lines.extend([
                (
                    f"{position}. "
                    f"[{action.get('priority', 'WATCH')}] "
                    f"{action.get('title', 'Unknown product')}"
                ),
                (
                    f"   Game: "
                    f"{action.get('game_name', 'Unknown')}"
                ),
                (
                    f"   Action: "
                    f"{action.get('action', 'MONITOR')}"
                ),
                (
                    f"   Reason: "
                    f"{action.get('reason', 'No reason recorded.')}"
                ),
                (
                    f"   Opportunity: "
                    f"{action.get('opportunity_score', 0)}/100"
                ),
                (
                    f"   Price: "
                    f"{format_price(action)}"
                ),
                (
                    f"   Availability: "
                    f"{display_value(action.get('availability'))}"
                ),
                (
                    f"   Release: "
                    f"{display_value(action.get('release_date'))}"
                ),
                (
                    f"   URL: "
                    f"{display_value(action.get('url'))}"
                ),
                "",
            ])

        lines.extend([
            "=" * 72,
            "URGENT CHANGE ALERTS",
            "=" * 72,
        ])

        if not urgent_alerts:
            lines.append(
                "No active change alerts."
            )

        for position, alert in enumerate(
            urgent_alerts[:10],
            start=1,
        ):
            lines.extend([
                (
                    f"{position}. "
                    f"[{alert.get('priority', 'LOW')}] "
                    f"{alert.get('title', 'Unknown product')}"
                ),
                (
                    f"   Event: "
                    f"{alert.get('event', 'UNKNOWN')}"
                ),
                (
                    f"   Alert score: "
                    f"{alert.get('score', 0)}/100"
                ),
                (
                    f"   Action: "
                    f"{alert.get('action', 'MONITOR')}"
                ),
                (
                    f"   Reason: "
                    f"{alert.get('reason', 'No reason recorded.')}"
                ),
                "",
            ])

        lines.extend([
            "=" * 72,
            "TOP OPPORTUNITIES OVERALL",
            "=" * 72,
        ])

        lines.extend(
            render_product_section(
                brief.get(
                    "top_overall",
                    [],
                )[:overall_limit]
            )
        )

        lines.extend([
            "=" * 72,
            "TOP QUICK FLIPS",
            "=" * 72,
        ])

        lines.extend(
            render_product_section(
                brief.get(
                    "top_flips",
                    [],
                )[:strategy_limit],
                featured_score=(
                    "flip_score"
                ),
            )
        )

        lines.extend([
            "=" * 72,
            "TOP LONG-TERM HOLDS",
            "=" * 72,
        ])

        lines.extend(
            render_product_section(
                brief.get(
                    "top_holds",
                    [],
                )[:strategy_limit],
                featured_score=(
                    "hold_score"
                ),
            )
        )

        lines.extend([
            "=" * 72,
            "TOP SLEEPER WATCHES",
            "=" * 72,
        ])

        lines.extend(
            render_product_section(
                brief.get(
                    "top_sleepers",
                    [],
                )[:strategy_limit],
                featured_score=(
                    "sleeper_score"
                ),
            )
        )

        lines.extend([
            "=" * 72,
            "LEADERS BY GAME",
            "=" * 72,
        ])

        category_leaders = (
            brief.get(
                "category_leaders",
                {},
            )
        )

        if not category_leaders:
            lines.append(
                "No category leaders available."
            )

        for category in [
            "pokemon",
            "lorcana",
            "one_piece",
        ]:
            product = (
                category_leaders.get(
                    category
                )
            )

            if not product:
                continue

            lines.extend([
                (
                    f"{GAME_NAMES.get(category, category.title())}:"
                ),
                (
                    f"   "
                    f"{product.get('title', 'Unknown product')}"
                ),
                (
                    f"   Opportunity: "
                    f"{product.get('opportunity_score', 0)}/100 "
                    f"({product.get('opportunity_tier', 'WATCH')})"
                ),
                (
                    f"   Strategy: "
                    f"{strategy_name(product)}"
                ),
                "",
            ])

        quality = (
            brief.get(
                "data_quality",
                {},
            )
        )

        lines.extend([
            "=" * 72,
            "DATA QUALITY",
            "=" * 72,
            (
                f"Products analyzed: "
                f"{quality.get('total', 0)}"
            ),
            (
                f"Known retail prices: "
                f"{quality.get('known_price_count', 0)}"
            ),
            (
                f"Known availability: "
                f"{quality.get('known_availability_count', 0)}"
            ),
            (
                f"Known release dates: "
                f"{quality.get('known_release_date_count', 0)}"
            ),
            (
                f"Known images: "
                f"{quality.get('known_image_count', 0)}"
            ),
            (
                f"Complete core records: "
                f"{quality.get('complete_core_count', 0)}"
            ),
            (
                f"Data completeness: "
                f"{quality.get('completeness_score', 0)}/100"
            ),
        ])

        missing_items = (
            quality.get(
                "highest_priority_missing_data",
                [],
            )
        )

        if missing_items:
            lines.extend([
                "",
                "High-priority products missing data:",
            ])

            for item in missing_items[:10]:
                lines.append(
                    (
                        f"- {item.get('title', 'Unknown')}: "
                        f"{', '.join(item.get('missing_fields', []))}"
                    )
                )

        return "\n".join(
            lines
        )


def build_action_queue(
    urgent_alerts,
    top_overall,
):
    actions_by_key = {}

    for alert in urgent_alerts:
        if alert.get(
            "priority"
        ) not in {
            "CRITICAL",
            "HIGH",
        }:
            continue

        key = action_key(
            alert
        )

        if not key:
            continue

        action = {
            "title": alert.get(
                "title"
            ),
            "category": alert.get(
                "category"
            ),
            "game_name": (
                alert.get(
                    "game_name"
                )
                or game_name(
                    alert
                )
            ),
            "priority": alert.get(
                "priority",
                "HIGH",
            ),
            "action": alert.get(
                "action",
                "REVIEW NOW",
            ),
            "reason": alert.get(
                "reason",
                "Important product change detected.",
            ),
            "opportunity_score": (
                alert.get(
                    "opportunity_score",
                    0,
                )
            ),
            "retail_price": (
                alert.get(
                    "retail_price"
                )
            ),
            "currency": alert.get(
                "currency"
            ),
            "availability": (
                alert.get(
                    "availability"
                )
            ),
            "release_date": (
                alert.get(
                    "release_date"
                )
            ),
            "url": alert.get(
                "url"
            ),
            "source": "alert",
        }

        actions_by_key[key] = (
            merge_action(
                existing=(
                    actions_by_key.get(
                        key
                    )
                ),
                incoming=action,
            )
        )

    for item in top_overall:
        tier = item.get(
            "opportunity_tier",
            "WATCH",
        )

        if tier not in {
            "CRITICAL",
            "HIGH",
        }:
            continue

        key = action_key(
            item
        )

        if not key:
            continue

        action = {
            "title": item.get(
                "title"
            ),
            "category": item.get(
                "category"
            ),
            "game_name": (
                item.get(
                    "game_name"
                )
                or game_name(
                    item
                )
            ),
            "priority": tier,
            "action": item.get(
                "recommended_action",
                "REVIEW OPPORTUNITY",
            ),
            "reason": (
                first_reason(
                    item.get(
                        "money_board_reasons"
                    )
                )
            ),
            "opportunity_score": (
                item.get(
                    "opportunity_score",
                    0,
                )
            ),
            "retail_price": (
                item.get(
                    "retail_price"
                )
            ),
            "currency": item.get(
                "currency"
            ),
            "availability": (
                item.get(
                    "availability"
                )
            ),
            "release_date": (
                item.get(
                    "release_date"
                )
            ),
            "url": item.get(
                "url"
            ),
            "source": (
                "money_board"
            ),
        }

        actions_by_key[key] = (
            merge_action(
                existing=(
                    actions_by_key.get(
                        key
                    )
                ),
                incoming=action,
            )
        )

    return sorted(
        actions_by_key.values(),
        key=lambda item: (
            PRIORITY_ORDER.get(
                item.get(
                    "priority",
                    "WATCH",
                ),
                0,
            ),
            number_value(
                item.get(
                    "opportunity_score"
                )
            ),
        ),
        reverse=True,
    )[:20]


def merge_action(
    existing,
    incoming,
):
    if existing is None:
        return dict(
            incoming
        )

    existing_priority = (
        PRIORITY_ORDER.get(
            existing.get(
                "priority",
                "WATCH",
            ),
            0,
        )
    )

    incoming_priority = (
        PRIORITY_ORDER.get(
            incoming.get(
                "priority",
                "WATCH",
            ),
            0,
        )
    )

    if incoming_priority > existing_priority:
        primary = dict(
            incoming
        )

        secondary = existing

    else:
        primary = dict(
            existing
        )

        secondary = incoming

    for key, value in (
        secondary.items()
    ):
        if primary.get(key) in (
            None,
            "",
            0,
            [],
            {},
        ) and value not in (
            None,
            "",
            [],
            {},
        ):
            primary[key] = value

    if (
        existing.get("source")
        == "alert"
        or incoming.get("source")
        == "alert"
    ):
        alert_action = (
            existing
            if existing.get("source")
            == "alert"
            else incoming
        )

        primary["action"] = (
            alert_action.get(
                "action"
            )
            or primary.get(
                "action"
            )
        )

        primary["reason"] = (
            alert_action.get(
                "reason"
            )
            or primary.get(
                "reason"
            )
        )

        primary["source"] = "alert"

    primary[
        "opportunity_score"
    ] = max(
        number_value(
            existing.get(
                "opportunity_score"
            )
        ),
        number_value(
            incoming.get(
                "opportunity_score"
            )
        ),
    )

    return primary


def build_category_leaders(items):
    leaders = {}

    for item in items:
        category = normalized_category(
            item
        )

        if (
            category
            and category not in leaders
        ):
            leaders[category] = item

    return leaders


def calculate_data_quality(items):
    total = len(items)

    known_price = 0
    known_availability = 0
    known_release_date = 0
    known_image = 0
    complete_core = 0
    missing_records = []

    for item in items:
        missing = []

        if item.get(
            "retail_price"
        ) in (
            None,
            "",
        ):
            missing.append(
                "retail_price"
            )

        else:
            known_price += 1

        if not item.get(
            "availability"
        ):
            missing.append(
                "availability"
            )

        else:
            known_availability += 1

        if not item.get(
            "release_date"
        ):
            missing.append(
                "release_date"
            )

        else:
            known_release_date += 1

        if not item.get(
            "image_url"
        ):
            missing.append(
                "image_url"
            )

        else:
            known_image += 1

        if not missing:
            complete_core += 1

        if missing:
            missing_records.append({
                "title": item.get(
                    "title",
                    "Unknown product",
                ),
                "category": (
                    normalized_category(
                        item
                    )
                ),
                "opportunity_score": (
                    item.get(
                        "opportunity_score",
                        strategy_score(
                            item
                        ),
                    )
                ),
                "missing_fields": (
                    missing
                ),
            })

    possible_fields = (
        total * 4
    )

    known_fields = (
        known_price
        + known_availability
        + known_release_date
        + known_image
    )

    completeness_score = (
        round(
            known_fields
            / possible_fields
            * 100
        )
        if possible_fields
        else 0
    )

    missing_records.sort(
        key=lambda item: (
            number_value(
                item.get(
                    "opportunity_score"
                )
            ),
            -len(
                item.get(
                    "missing_fields",
                    [],
                )
            ),
        ),
        reverse=True,
    )

    return {
        "total": total,
        "known_price_count": (
            known_price
        ),
        "known_availability_count": (
            known_availability
        ),
        "known_release_date_count": (
            known_release_date
        ),
        "known_image_count": (
            known_image
        ),
        "complete_core_count": (
            complete_core
        ),
        "completeness_score": (
            completeness_score
        ),
        "highest_priority_missing_data": (
            missing_records[:20]
        ),
    }


def rank_alerts(alerts):
    return sorted(
        alerts,
        key=lambda alert: (
            PRIORITY_ORDER.get(
                alert.get(
                    "priority",
                    "IGNORE",
                ),
                0,
            ),
            number_value(
                alert.get(
                    "score"
                )
            ),
            number_value(
                alert.get(
                    "opportunity_score"
                )
            ),
        ),
        reverse=True,
    )


def render_product_section(
    items,
    featured_score=(
        "opportunity_score"
    ),
):
    lines = []

    if not items:
        return [
            "No products available.",
            "",
        ]

    for position, item in enumerate(
        items,
        start=1,
    ):
        lines.extend([
            (
                f"{position}. "
                f"{item.get('title', 'Unknown product')}"
            ),
            (
                f"   Game: "
                f"{item.get('game_name') or game_name(item)}"
            ),
            (
                f"   Opportunity: "
                f"{item.get('opportunity_score', 0)}/100 "
                f"({item.get('opportunity_tier', 'WATCH')})"
            ),
            (
                f"   Featured score: "
                f"{item.get(featured_score, 0)}/100"
            ),
            (
                f"   Strategy: "
                f"{strategy_name(item)}"
            ),
            (
                f"   Price: "
                f"{format_price(item)}"
            ),
            (
                f"   Availability: "
                f"{display_value(item.get('availability'))}"
            ),
            (
                f"   Release: "
                f"{display_value(item.get('release_date'))}"
            ),
            "",
        ])

    return lines


def strategy_name(item):
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
        return strategy.get(
            "strategy",
            "UNKNOWN",
        )

    return str(
        strategy
    )


def strategy_score(item):
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
        return number_value(
            strategy.get(
                "score"
            )
        )

    return 0


def normalized_category(item):
    return (
        str(
            item.get(
                "category"
            )
            or item.get(
                "tcg_name"
            )
            or category_from_product_key(
                item.get(
                    "product_key"
                )
            )
            or ""
        )
        .strip()
        .lower()
    )


def game_name(item):
    category = (
        normalized_category(
            item
        )
    )

    return GAME_NAMES.get(
        category,
        category.replace(
            "_",
            " ",
        ).title()
        if category
        else "Unknown",
    )


def action_key(item):
    category = (
        normalized_category(
            item
        )
    )

    sku = normalize_sku(
        item.get(
            "sku"
        )
    )

    if sku:
        return (
            f"{category}:sku:{sku}"
        )

    product_key = normalize_product_key(
        item.get(
            "product_key"
        )
        or item.get(
            "catalog_key"
        )
    )

    if product_key:
        return product_key

    url = normalize_url(
        item.get(
            "url"
        )
    )

    if url:
        return (
            f"{category}:url:{url}"
        )

    title = normalize_title(
        item.get(
            "title"
        )
    )

    if title:
        return (
            f"{category}:title:{title}"
        )

    return None


def normalize_product_key(value):
    text = str(
        value or ""
    ).strip().lower()

    if not text:
        return None

    parts = text.split(
        ":"
    )

    if (
        len(parts) >= 3
        and parts[1] == "sku"
    ):
        category = (
            parts[0]
            .strip()
            .replace("-", "_")
            .replace(" ", "_")
        )

        sku = normalize_sku(
            ":".join(
                parts[2:]
            )
        )

        if sku:
            return (
                f"{category}:sku:{sku}"
            )

    if (
        len(parts) >= 3
        and parts[1] == "url"
    ):
        category = (
            parts[0]
            .strip()
            .replace("-", "_")
            .replace(" ", "_")
        )

        url = normalize_url(
            ":".join(
                parts[2:]
            )
        )

        if url:
            return (
                f"{category}:url:{url}"
            )

    return text


def category_from_product_key(value):
    text = str(
        value or ""
    ).strip().lower()

    if ":" not in text:
        return ""

    return (
        text.split(
            ":",
            1,
        )[0]
        .replace("-", "_")
        .replace(" ", "_")
    )


def normalize_sku(value):
    text = (
        str(value or "")
        .strip()
        .lower()
    )

    if not text:
        return ""

    text = re.sub(
        r"[\s_]+",
        "-",
        text,
    )

    text = re.sub(
        r"[^a-z0-9-]+",
        "",
        text,
    )

    text = re.sub(
        r"-+",
        "-",
        text,
    )

    return text.strip(
        "-"
    )


def normalize_url(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .split("#")[0]
        .rstrip("/")
    )


def normalize_title(value):
    text = (
        str(value or "")
        .strip()
        .lower()
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


def first_reason(value):
    if isinstance(
        value,
        list,
    ) and value:
        return str(
            value[0]
        )

    if value:
        return str(
            value
        )

    return (
        "Strong combined TCG "
        "opportunity score."
    )


def format_price(item):
    value = item.get(
        "retail_price"
    )

    if value in (
        None,
        "",
    ):
        return "Unknown"

    try:
        amount = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return str(
            value
        )

    currency = (
        item.get(
            "currency"
        )
        or "USD"
    )

    if currency == "USD":
        return f"${amount:.2f}"

    return (
        f"{amount:.2f} "
        f"{currency}"
    )


def display_value(value):
    if value in (
        None,
        "",
    ):
        return "Unknown"

    return str(
        value
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