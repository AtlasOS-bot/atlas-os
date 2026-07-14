from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)


def test_catalog_creates_and_updates_product(
    tmp_path,
):
    path = (
        tmp_path
        / "tcg_catalog.json"
    )

    store = TcgCatalogStore(
        path=path
    )

    first_item = {
        "title": (
            "ONE PIECE Premium "
            "Card Collection"
        ),
        "category": "one_piece",
        "sku": "OP-PCC-100",
        "collector_score": 70,
        "hold_score": 72,
        "flip_score": 60,
        "sources": [
            "one_piece_products",
        ],
        "best_strategy": {
            "strategy": (
                "LONG-TERM HOLD"
            ),
            "score": 72,
        },
    }

    first_result = (
        store.upsert_many([
            first_item,
        ])
    )

    assert (
        first_result[
            "created_this_scan"
        ]
        == 1
    )

    assert (
        first_result["count"]
        == 1
    )

    updated_item = {
        "title": (
            "ONE PIECE Premium "
            "Card Collection"
        ),
        "category": "one_piece",
        "sku": "OP-PCC-100",
        "collector_score": 82,
        "hold_score": 88,
        "flip_score": 75,
        "sources": [
            "premium_bandai_one_piece",
        ],
        "best_strategy": {
            "strategy": (
                "LONG-TERM HOLD"
            ),
            "score": 88,
        },
    }

    second_result = (
        store.upsert_many([
            updated_item,
        ])
    )

    assert (
        second_result[
            "created_this_scan"
        ]
        == 0
    )

    assert (
        second_result[
            "updated_this_scan"
        ]
        == 1
    )

    assert (
        second_result["count"]
        == 1
    )

    saved = store.all()[0]

    assert (
        saved["collector_score"]
        == 82
    )

    assert set(
        saved["sources"]
    ) == {
        "one_piece_products",
        "premium_bandai_one_piece",
    }

    assert (
        saved["scan_count"]
        == 2
    )


def test_catalog_ranks_stronger_item_first(
    tmp_path,
):
    store = TcgCatalogStore(
        path=(
            tmp_path
            / "tcg_catalog.json"
        )
    )

    store.upsert_many([
        {
            "title": "Basic Product",
            "category": "one_piece",
            "url": (
                "https://example.com/basic"
            ),
            "collector_score": 30,
            "best_strategy": {
                "strategy": (
                    "SLEEPER WATCH"
                ),
                "score": 35,
            },
        },
        {
            "title": "Elite Product",
            "category": "one_piece",
            "url": (
                "https://example.com/elite"
            ),
            "collector_score": 90,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 94,
            },
        },
    ])

    top = store.top(
        limit=1,
        category="one_piece",
    )

    assert (
        top[0]["title"]
        == "Elite Product"
    )