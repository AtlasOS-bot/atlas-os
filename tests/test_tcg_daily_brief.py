from scouts.tcg.daily_brief import (
    TcgDailyBrief,
)


def test_daily_brief_builds_action_queue():
    catalog_items = [
        {
            "title": (
                "One Piece Premium Set"
            ),
            "category": "one_piece",
            "sku": "OP-DAILY-1",
            "retail_price": 29.99,
            "currency": "USD",
            "availability": "InStock",
            "release_date": (
                "2026-08-01"
            ),
            "image_url": (
                "https://example.com/op.jpg"
            ),
            "collector_score": 90,
            "flip_score": 88,
            "hold_score": 92,
            "sleeper_score": 35,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 92,
            },
        }
    ]

    money_board = {
        "items": [
            {
                **catalog_items[0],
                "game_name": (
                    "One Piece"
                ),
                "opportunity_score": 91,
                "opportunity_tier": (
                    "CRITICAL"
                ),
                "recommended_action": (
                    "PRIORITIZE FOR HOLD"
                ),
                "money_board_reasons": [
                    (
                        "Strong collector and "
                        "hold opportunity."
                    )
                ],
            }
        ],
        "top_flips": [],
        "top_holds": [],
        "top_sleepers": [],
        "critical_count": 1,
        "high_count": 0,
        "medium_count": 0,
        "watch_count": 0,
    }

    alerts = [
        {
            "title": (
                "One Piece Premium Set"
            ),
            "category": "one_piece",
            "game_name": "One Piece",
            "product_key": (
                "one_piece:sku:op-daily-1"
            ),
            "priority": "CRITICAL",
            "event": "RESTOCK",
            "score": 94,
            "action": (
                "CHECK STOCK AND BUY QUICKLY"
            ),
            "reason": (
                "The product returned to stock."
            ),
            "opportunity_score": 91,
            "url": (
                "https://example.com/op"
            ),
        }
    ]

    brief = TcgDailyBrief.build(
        catalog_items=(
            catalog_items
        ),
        money_board=(
            money_board
        ),
        active_alerts=alerts,
        generated_at=(
            "2026-07-14T18:00:00+00:00"
        ),
    )

    assert (
        brief["summary"][
            "catalog_count"
        ]
        == 1
    )

    assert (
        len(
            brief[
                "action_queue"
            ]
        )
        == 1
    )

    assert (
        brief[
            "action_queue"
        ][0]["priority"]
        == "CRITICAL"
    )


def test_daily_brief_identifies_missing_data():
    catalog_items = [
        {
            "title": (
                "Lorcana Mystery Product"
            ),
            "category": "lorcana",
            "collector_score": 70,
            "best_strategy": {
                "strategy": (
                    "SLEEPER WATCH"
                ),
                "score": 65,
            },
        }
    ]

    money_board = {
        "items": [],
        "top_flips": [],
        "top_holds": [],
        "top_sleepers": [],
    }

    brief = TcgDailyBrief.build(
        catalog_items=(
            catalog_items
        ),
        money_board=(
            money_board
        ),
        active_alerts=[],
    )

    quality = brief[
        "data_quality"
    ]

    assert (
        quality[
            "completeness_score"
        ]
        == 0
    )

    missing = quality[
        "highest_priority_missing_data"
    ][0]["missing_fields"]

    assert (
        "retail_price"
        in missing
    )

    assert (
        "availability"
        in missing
    )

    assert (
        "release_date"
        in missing
    )


def test_daily_brief_renders_sections():
    brief = {
        "generated_at": (
            "2026-07-14T18:00:00+00:00"
        ),
        "summary": {
            "catalog_count": 1,
            "ranked_count": 1,
            "active_alert_count": 0,
            "critical_count": 0,
            "high_count": 1,
            "medium_count": 0,
            "watch_count": 0,
        },
        "action_queue": [],
        "urgent_alerts": [],
        "top_overall": [],
        "top_flips": [],
        "top_holds": [],
        "top_sleepers": [],
        "category_leaders": {},
        "data_quality": {
            "total": 1,
            "known_price_count": 0,
            "known_availability_count": 0,
            "known_release_date_count": 0,
            "known_image_count": 0,
            "complete_core_count": 0,
            "completeness_score": 0,
            "highest_priority_missing_data": [],
        },
    }

    rendered = (
        TcgDailyBrief.render(
            brief
        )
    )

    assert (
        "ATLAS CROSS-TCG "
        "DAILY COMMAND BRIEF"
        in rendered
    )

    assert (
        "TODAY'S ACTION QUEUE"
        in rendered
    )

    assert (
        "DATA QUALITY"
        in rendered
    )