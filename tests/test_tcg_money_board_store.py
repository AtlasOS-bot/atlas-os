from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)
from scouts.tcg.money_board_store import (
    TcgMoneyBoardStore,
)


def test_money_board_store_generates_file(
    tmp_path,
):
    catalog_path = (
        tmp_path
        / "catalog.json"
    )

    money_board_path = (
        tmp_path
        / "money_board.json"
    )

    catalog_store = TcgCatalogStore(
        path=catalog_path
    )

    catalog_store.upsert_many([
        {
            "title": "Premium Product",
            "category": "one_piece",
            "url": (
                "https://example.com/"
                "premium-product"
            ),
            "collector_score": 85,
            "popularity_score": 80,
            "flip_score": 82,
            "hold_score": 90,
            "sleeper_score": 40,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 90,
            },
        }
    ])

    board_store = (
        TcgMoneyBoardStore(
            path=money_board_path,
            catalog_store=(
                catalog_store
            ),
        )
    )

    board = board_store.generate()

    loaded = board_store.load()

    assert board["count"] == 1
    assert loaded["count"] == 1

    assert (
        loaded["top_overall"][0][
            "title"
        ]
        == "Premium Product"
    )