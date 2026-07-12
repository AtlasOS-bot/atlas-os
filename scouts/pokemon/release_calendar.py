from datetime import date, datetime, timezone


ACTION_PRIORITY = {
    "RELEASE DAY": 7,
    "PREORDER NOW": 6,
    "BUY THIS WEEK": 5,
    "NEWLY RELEASED": 4,
    "MONITOR": 3,
    "PAST RELEASE": 2,
    "DATE UNKNOWN": 1,
}


def build_release_calendar(items, today=None):
    today = today or datetime.now(
        timezone.utc
    ).date()

    entries = []

    for item in items:
        entry = build_release_entry(
            item=item,
            today=today,
        )

        entries.append(entry)

    return sorted(
        entries,
        key=release_sort_key,
    )


def build_release_entry(item, today=None):
    today = today or datetime.now(
        timezone.utc
    ).date()

    release_date = parse_release_date(
        item.get("release_date")
    )

    if release_date is None:
        return {
            "title": item.get(
                "title",
                "Unknown product",
            ),
            "url": item.get("url"),
            "product_type": item.get(
                "product_type",
                "other",
            ),
            "release_date": None,
            "days_until_release": None,
            "action_window": "DATE UNKNOWN",
            "urgency_score": 10,
            "reason": (
                "Atlas has not found a reliable "
                "release date for this product."
            ),
            "recommended_action": (
                "CONTINUE MONITORING"
            ),
            "collector_score": item.get(
                "collector_score",
                0,
            ),
            "flip_score": item.get(
                "flip_score",
                0,
            ),
            "hold_score": item.get(
                "hold_score",
                0,
            ),
            "popularity_score": item.get(
                "popularity_score",
                0,
            ),
            "availability": item.get(
                "availability"
            ),
        }

    days_until_release = (
        release_date - today
    ).days

    action = determine_action_window(
        days_until_release=days_until_release,
        item=item,
    )

    return {
        "title": item.get(
            "title",
            "Unknown product",
        ),
        "url": item.get("url"),
        "product_type": item.get(
            "product_type",
            "other",
        ),
        "release_date": (
            release_date.isoformat()
        ),
        "days_until_release": (
            days_until_release
        ),
        "action_window": action[
            "action_window"
        ],
        "urgency_score": action[
            "urgency_score"
        ],
        "reason": action["reason"],
        "recommended_action": action[
            "recommended_action"
        ],
        "collector_score": item.get(
            "collector_score",
            0,
        ),
        "flip_score": item.get(
            "flip_score",
            0,
        ),
        "hold_score": item.get(
            "hold_score",
            0,
        ),
        "popularity_score": item.get(
            "popularity_score",
            0,
        ),
        "availability": item.get(
            "availability"
        ),
    }


def determine_action_window(
    days_until_release,
    item,
):
    availability = normalize_availability(
        item.get("availability")
    )

    flip_score = item.get(
        "flip_score",
        0,
    )

    collector_score = item.get(
        "collector_score",
        0,
    )

    if days_until_release == 0:
        return {
            "action_window": "RELEASE DAY",
            "urgency_score": 100,
            "reason": (
                "The official release date is today."
            ),
            "recommended_action": (
                "CHECK STOCK IMMEDIATELY"
            ),
        }

    if 1 <= days_until_release <= 3:
        return {
            "action_window": "PREORDER NOW",
            "urgency_score": 95,
            "reason": (
                f"The product releases in "
                f"{days_until_release} day(s)."
            ),
            "recommended_action": (
                "CHECK PREORDERS AND PURCHASE LIMITS"
            ),
        }

    if 4 <= days_until_release <= 7:
        return {
            "action_window": "BUY THIS WEEK",
            "urgency_score": 85,
            "reason": (
                f"The product releases within "
                f"{days_until_release} days."
            ),
            "recommended_action": (
                "PREPARE PURCHASE PLAN"
            ),
        }

    if 8 <= days_until_release <= 21:
        action = (
            "TRACK PREORDERS"
            if (
                flip_score >= 70
                or collector_score >= 70
            )
            else "CONTINUE MONITORING"
        )

        return {
            "action_window": "MONITOR",
            "urgency_score": 65,
            "reason": (
                f"The product releases in "
                f"{days_until_release} days."
            ),
            "recommended_action": action,
        }

    if days_until_release > 21:
        return {
            "action_window": "MONITOR",
            "urgency_score": 35,
            "reason": (
                f"The product releases in "
                f"{days_until_release} days."
            ),
            "recommended_action": (
                "ADD TO RELEASE WATCHLIST"
            ),
        }

    days_since_release = abs(
        days_until_release
    )

    if days_since_release <= 3:
        action = (
            "CHECK SECONDARY MARKET"
            if availability in {
                "soldout",
                "outofstock",
            }
            else "CHECK REMAINING STOCK"
        )

        return {
            "action_window": "NEWLY RELEASED",
            "urgency_score": 80,
            "reason": (
                f"The product released "
                f"{days_since_release} day(s) ago."
            ),
            "recommended_action": action,
        }

    if days_since_release <= 14:
        return {
            "action_window": "NEWLY RELEASED",
            "urgency_score": 55,
            "reason": (
                f"The product released "
                f"{days_since_release} days ago."
            ),
            "recommended_action": (
                "REVIEW DEMAND AND AVAILABILITY"
            ),
        }

    return {
        "action_window": "PAST RELEASE",
        "urgency_score": 20,
        "reason": (
            f"The product released "
            f"{days_since_release} days ago."
        ),
        "recommended_action": (
            "MONITOR LONG-TERM PERFORMANCE"
        ),
    }


def release_sort_key(entry):
    days = entry.get(
        "days_until_release"
    )

    if days is None:
        date_position = 999999
    elif days >= 0:
        date_position = days
    else:
        date_position = (
            10000 + abs(days)
        )

    return (
        -ACTION_PRIORITY.get(
            entry.get(
                "action_window",
                "DATE UNKNOWN",
            ),
            0,
        ),
        date_position,
        -(
            entry.get(
                "urgency_score",
                0,
            )
            or 0
        ),
        -(
            entry.get(
                "collector_score",
                0,
            )
            or 0
        ),
    )


def parse_release_date(value):
    if not value:
        return None

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    for candidate in [
        text,
        text[:10],
    ]:
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


def normalize_availability(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )