from scouts.tcg.alert_brief import (
    TcgAlertBrief,
)
from scouts.tcg.alert_intelligence import (
    analyze_tcg_alert,
)
from scouts.tcg.alert_store import (
    TcgAlertStore,
)
from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)
from scouts.tcg.money_board import (
    TcgMoneyBoard,
)
from scouts.tcg.money_board_store import (
    TcgMoneyBoardStore,
)
from scouts.tcg.state_tracker import (
    TcgStateTracker,
)


def run_alert_scan():
    catalog_store = (
        TcgCatalogStore()
    )

    raw_items = (
        catalog_store.all()
    )

    board = TcgMoneyBoard.build(
        raw_items
    )

    ranked_items = board.get(
        "items",
        [],
    )

    state_tracker = (
        TcgStateTracker()
    )

    alert_store = (
        TcgAlertStore()
    )

    observations = (
        state_tracker.observe_many(
            ranked_items
        )
    )

    item_by_key = {}

    for item in ranked_items:
        product_key = (
            TcgCatalogStore.product_key(
                item
            )
        )

        if product_key:
            item_by_key[
                product_key
            ] = item

    created_count = 0

    for observation in observations:
        if not observation.get(
            "has_change"
        ):
            continue

        product_key = (
            observation[
                "product_key"
            ]
        )

        item = item_by_key.get(
            product_key,
            {},
        )

        for change in observation.get(
            "changes",
            [],
        ):
            alert = analyze_tcg_alert(
                item=item,
                change=change,
            )

            saved = alert_store.save(
                item=item,
                product_key=(
                    product_key
                ),
                alert=alert,
            )

            if saved:
                created_count += 1

    money_board_store = (
        TcgMoneyBoardStore()
    )

    money_board_store.save(
        board
    )

    active_alerts = (
        alert_store.active()
    )

    return {
        "products_checked": len(
            ranked_items
        ),
        "observations": (
            observations
        ),
        "created_count": (
            created_count
        ),
        "active_alerts": (
            active_alerts
        ),
        "board": board,
    }


def main():
    result = run_alert_scan()

    print("")
    print(
        "CROSS-TCG CHANGE SCAN"
    )
    print("---------------------")

    print(
        "Products checked:",
        result[
            "products_checked"
        ],
    )

    print(
        "New alerts created:",
        result[
            "created_count"
        ],
    )

    print(
        "Active alerts:",
        len(
            result[
                "active_alerts"
            ]
        ),
    )

    print("")

    print(
        TcgAlertBrief.generate(
            alerts=result[
                "active_alerts"
            ],
            limit=20,
        )
    )

    print("")
    print(
        "Alert data saved to:"
    )

    print(
        ".atlas_data/"
        "tcg_alerts.json"
    )

    print(
        ".atlas_data/"
        "tcg_product_states.json"
    )


if __name__ == "__main__":
    main()