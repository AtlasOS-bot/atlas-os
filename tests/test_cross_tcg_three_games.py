from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)
from scouts.tcg.money_board_store import (
    TcgMoneyBoardStore,
)


def test_catalog_and_board_support_three_games(
    tmp_path,
):
    catalog_path = (
        tmp_path
        / "tcg_catalog.json"
    )

    board_path = (
        tmp_path
        / "tcg_money_board.json"
    )

    catalog = TcgCatalogStore(
        path=catalog_path
    )

    catalog.upsert_many([
        {
            "title": (
                "Pokémon Center "
                "Elite Trainer Box"
            ),
            "category": "pokemon",
            "sku": "PKM-001",
            "collector_score": 90,
            "popularity_score": 85,
            "flip_score": 82,
            "hold_score": 94,
            "sleeper_score": 35,
            "limited_release": True,
            "promo_included": True,
            "sealed_product": True,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 94,
            },
        },
        {
            "title": (
                "Disney Lorcana "
                "Collector Gift Set"
            ),
            "category": "lorcana",
            "sku": "LOR-001",
            "collector_score": 88,
            "popularity_score": 82,
            "flip_score": 86,
            "hold_score": 90,
            "sleeper_score": 40,
            "collector_variant": True,
            "limited_release": True,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 90,
            },
        },
        {
            "title": (
                "One Piece Premium "
                "Card Collection"
            ),
            "category": "one_piece",
            "sku": "OP-001",
            "collector_score": 92,
            "popularity_score": 87,
            "flip_score": 90,
            "hold_score": 93,
            "sleeper_score": 38,
            "limited_release": True,
            "promo_included": True,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 93,
            },
        },
    ])

    board_store = (
        TcgMoneyBoardStore(
            path=board_path,
            catalog_store=catalog,
        )
    )

    board = board_store.generate()

    assert board["count"] == 3

    assert set(
        board["by_category"].keys()
    ) == {
        "pokemon",
        "lorcana",
        "one_piece",
    }

    game_names = {
        item["game_name"]
        for item in board["items"]
    }

    assert "Pokémon" in game_names

    assert (
        "Disney Lorcana"
        in game_names
    )

    assert (
        "One Piece"
        in game_names
    )


def test_pokemon_can_rank_first(
    tmp_path,
):
    catalog = TcgCatalogStore(
        path=(
            tmp_path
            / "catalog.json"
        )
    )

    catalog.upsert_many([
        {
            "title": "Basic Lorcana Deck",
            "category": "lorcana",
            "url": (
                "https://example.com/"
                "lorcana"
            ),
            "collector_score": 35,
            "popularity_score": 30,
            "flip_score": 32,
            "hold_score": 38,
            "sleeper_score": 45,
            "best_strategy": {
                "strategy": (
                    "SLEEPER WATCH"
                ),
                "score": 45,
            },
        },
        {
            "title": (
                "Pokémon Center "
                "Exclusive ETB"
            ),
            "category": "pokemon",
            "url": (
                "https://example.com/"
                "pokemon"
            ),
            "collector_score": 96,
            "popularity_score": 94,
            "flip_score": 91,
            "hold_score": 98,
            "sleeper_score": 30,
            "limited_release": True,
            "promo_included": True,
            "sealed_product": True,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 98,
            },
        },
    ])

    board_store = (
        TcgMoneyBoardStore(
            path=(
                tmp_path
                / "board.json"
            ),
            catalog_store=catalog,
        )
    )

    board = board_store.generate()

    assert (
        board["top_overall"][0][
            "title"
        ]
        == (
            "Pokémon Center "
            "Exclusive ETB"
        )
    )

    assert (
        board["top_overall"][0][
            "game_name"
        ]
        == "Pokémon"
    )