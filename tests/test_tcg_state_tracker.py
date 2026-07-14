from scouts.tcg.state_tracker import (
    TcgStateTracker,
)


def test_first_observation_is_new_product(
    tmp_path,
):
    tracker = TcgStateTracker(
        path=(
            tmp_path
            / "states.json"
        )
    )

    items = [
        {
            "title": (
                "One Piece Premium Set"
            ),
            "category": "one_piece",
            "sku": "OP-TEST-1",
            "availability": "InStock",
            "retail_price": 29.99,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 80,
            },
        }
    ]

    result = tracker.observe_many(
        items
    )

    assert len(result) == 1

    assert result[0][
        "has_change"
    ] is True

    assert result[0][
        "changes"
    ][0]["event"] == (
        "NEW_PRODUCT"
    )


def test_restock_is_detected(
    tmp_path,
):
    tracker = TcgStateTracker(
        path=(
            tmp_path
            / "states.json"
        )
    )

    unavailable = {
        "title": "Lorcana Gift Set",
        "category": "lorcana",
        "sku": "LOR-TEST-1",
        "availability": (
            "OutOfStock"
        ),
    }

    available = {
        "title": "Lorcana Gift Set",
        "category": "lorcana",
        "sku": "LOR-TEST-1",
        "availability": "InStock",
    }

    tracker.observe_many([
        unavailable,
    ])

    result = tracker.observe_many([
        available,
    ])

    events = {
        change["event"]
        for change in result[0][
            "changes"
        ]
    }

    assert "RESTOCK" in events


def test_price_drop_is_detected(
    tmp_path,
):
    tracker = TcgStateTracker(
        path=(
            tmp_path
            / "states.json"
        )
    )

    original = {
        "title": "Pokémon ETB",
        "category": "pokemon",
        "sku": "PKM-TEST-1",
        "retail_price": 59.99,
    }

    discounted = {
        "title": "Pokémon ETB",
        "category": "pokemon",
        "sku": "PKM-TEST-1",
        "retail_price": 49.99,
    }

    tracker.observe_many([
        original,
    ])

    result = tracker.observe_many([
        discounted,
    ])

    events = {
        change["event"]
        for change in result[0][
            "changes"
        ]
    }

    assert "PRICE_DROP" in events


def test_strategy_upgrade_is_detected(
    tmp_path,
):
    tracker = TcgStateTracker(
        path=(
            tmp_path
            / "states.json"
        )
    )

    first = {
        "title": "One Piece Box",
        "category": "one_piece",
        "sku": "OP-TEST-2",
        "best_strategy": {
            "strategy": (
                "SLEEPER WATCH"
            ),
            "score": 45,
        },
    }

    second = {
        "title": "One Piece Box",
        "category": "one_piece",
        "sku": "OP-TEST-2",
        "best_strategy": {
            "strategy": (
                "LONG-TERM HOLD"
            ),
            "score": 70,
        },
    }

    tracker.observe_many([
        first,
    ])

    result = tracker.observe_many([
        second,
    ])

    events = {
        change["event"]
        for change in result[0][
            "changes"
        ]
    }

    assert (
        "STRATEGY_UPGRADE"
        in events
    )