from scouts.tcg.money_board_store import (
    TcgMoneyBoardStore,
)
from scouts.tcg.money_brief import (
    TcgMoneyBrief,
)


def main():
    store = TcgMoneyBoardStore()

    board = store.generate()

    print(
        TcgMoneyBrief.generate(
            board=board,
            limit=20,
        )
    )

    print("")
    print(
        "Money board saved to:"
    )

    print(
        ".atlas_data/"
        "tcg_money_board.json"
    )


if __name__ == "__main__":
    main()