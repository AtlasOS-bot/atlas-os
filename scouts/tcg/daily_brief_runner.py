from scouts.tcg.alert_store import (
    TcgAlertStore,
)
from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)
from scouts.tcg.daily_brief import (
    TcgDailyBrief,
)
from scouts.tcg.daily_brief_store import (
    TcgDailyBriefStore,
)
from scouts.tcg.money_board import (
    TcgMoneyBoard,
)
from scouts.tcg.money_board_store import (
    TcgMoneyBoardStore,
)


def generate_daily_brief():
    catalog_store = (
        TcgCatalogStore()
    )

    alert_store = (
        TcgAlertStore()
    )

    money_board_store = (
        TcgMoneyBoardStore()
    )

    brief_store = (
        TcgDailyBriefStore()
    )

    catalog_items = (
        catalog_store.all()
    )

    money_board = (
        TcgMoneyBoard.build(
            catalog_items
        )
    )

    active_alerts = (
        alert_store.active()
    )

    brief = TcgDailyBrief.build(
        catalog_items=(
            catalog_items
        ),
        money_board=(
            money_board
        ),
        active_alerts=(
            active_alerts
        ),
    )

    money_board_store.save(
        money_board
    )

    saved_paths = brief_store.save(
        brief=brief,
        preserve_history=True,
    )

    return {
        "brief": brief,
        "saved_paths": (
            saved_paths
        ),
    }


def main():
    result = generate_daily_brief()

    brief = result[
        "brief"
    ]

    print(
        TcgDailyBrief.render(
            brief=brief,
            overall_limit=10,
            strategy_limit=5,
        )
    )

    print("")
    print(
        "Daily brief saved to:"
    )

    print(
        result[
            "saved_paths"
        ]["current_path"]
    )

    print(
        "History snapshot saved to:"
    )

    print(
        result[
            "saved_paths"
        ]["history_path"]
    )


if __name__ == "__main__":
    main()