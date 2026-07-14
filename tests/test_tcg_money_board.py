from scouts.tcg.money_board import (
    TcgMoneyBoard,
)


def test_money_board_ranks_best_item_first():
    items = [
        {
            "title": "Basic Starter Deck",
            "category": "one_piece",
            "collector_score": 35,
            "popularity_score": 30,
            "flip_score": 30,
            "hold_score": 35,
            "sleeper_score": 40,
            "best_strategy": {
                "strategy": (
                    "SLEEPER WATCH"
                ),
                "score": 40,
            },
        },
        {
            "title": (
                "Limited Collector Set"
            ),
            "category": "lorcana",
            "collector_score": 92,
            "popularity_score": 85,
            "flip_score": 88,
            "hold_score": 94,
            "sleeper_score": 45,
            "limited_release": True,
            "promo_included": True,
            "collector_variant": True,
            "sealed_product": True,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 94,
            },
        },
    ]

    board = TcgMoneyBoard.build(
        items
    )

    assert board["count"] == 2

    assert (
        board["top_overall"][0][
            "title"
        ]
        == "Limited Collector Set"
    )

    assert (
        board["top_overall"][0][
            "opportunity_score"
        ]
        >= 85
    )

    assert (
        board["top_overall"][0][
            "opportunity_tier"
        ]
        == "CRITICAL"
    )


def test_money_board_creates_strategy_lists():
    items = [
        {
            "title": "Flip Product",
            "category": "one_piece",
            "collector_score": 65,
            "popularity_score": 90,
            "flip_score": 95,
            "hold_score": 50,
            "sleeper_score": 20,
            "best_strategy": {
                "strategy": (
                    "QUICK FLIP"
                ),
                "score": 95,
            },
        },
        {
            "title": "Hold Product",
            "category": "lorcana",
            "collector_score": 90,
            "popularity_score": 65,
            "flip_score": 60,
            "hold_score": 97,
            "sleeper_score": 35,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 97,
            },
        },
    ]

    board = TcgMoneyBoard.build(
        items
    )

    assert (
        board["top_flips"][0][
            "title"
        ]
        == "Flip Product"
    )

    assert (
        board["top_holds"][0][
            "title"
        ]
        == "Hold Product"
    )


def test_money_board_groups_categories():
    items = [
        {
            "title": "One Piece Product",
            "category": "one_piece",
            "best_strategy": {
                "score": 50,
            },
        },
        {
            "title": "Lorcana Product",
            "category": "lorcana",
            "best_strategy": {
                "score": 50,
            },
        },
    ]

    board = TcgMoneyBoard.build(
        items
    )

    assert (
        "one_piece"
        in board["by_category"]
    )

    assert (
        "lorcana"
        in board["by_category"]
    )