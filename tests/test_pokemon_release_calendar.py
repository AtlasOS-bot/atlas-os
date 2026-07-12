from datetime import date, timedelta

from scouts.pokemon.release_calendar import (
    build_release_calendar,
    build_release_entry,
)


def test_release_today_gets_release_day_action():
    today = date(
        2026,
        7,
        11,
    )

    item = {
        "title": "Test Elite Trainer Box",
        "release_date": today.isoformat(),
        "product_type": (
            "elite_trainer_box"
        ),
    }

    entry = build_release_entry(
        item=item,
        today=today,
    )

    assert (
        entry["action_window"]
        == "RELEASE DAY"
    )

    assert (
        entry["recommended_action"]
        == "CHECK STOCK IMMEDIATELY"
    )


def test_upcoming_product_gets_buy_this_week():
    today = date(
        2026,
        7,
        11,
    )

    item = {
        "title": "Test Booster Bundle",
        "release_date": (
            today + timedelta(days=5)
        ).isoformat(),
        "product_type": (
            "booster_bundle"
        ),
    }

    entry = build_release_entry(
        item=item,
        today=today,
    )

    assert (
        entry["action_window"]
        == "BUY THIS WEEK"
    )

    assert (
        entry["days_until_release"]
        == 5
    )


def test_calendar_prioritizes_release_day():
    today = date(
        2026,
        7,
        11,
    )

    items = [
        {
            "title": "Future Product",
            "release_date": (
                today + timedelta(days=30)
            ).isoformat(),
        },
        {
            "title": "Today Product",
            "release_date": (
                today.isoformat()
            ),
        },
        {
            "title": "Unknown Product",
            "release_date": None,
        },
    ]

    calendar = build_release_calendar(
        items=items,
        today=today,
    )

    assert (
        calendar[0]["title"]
        == "Today Product"
    )