import json
import os
from pathlib import Path

from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)
from scouts.tcg.money_board import (
    TcgMoneyBoard,
)


DEFAULT_MONEY_BOARD_PATH = Path(
    os.environ.get(
        "ATLAS_TCG_MONEY_BOARD_PATH",
        ".atlas_data/tcg_money_board.json",
    )
)


class TcgMoneyBoardStore:

    def __init__(
        self,
        path=None,
        catalog_store=None,
    ):
        self.path = (
            Path(path)
            if path
            else DEFAULT_MONEY_BOARD_PATH
        )

        self.catalog_store = (
            catalog_store
            or TcgCatalogStore()
        )

    def generate(self):
        items = (
            self.catalog_store.all()
        )

        board = TcgMoneyBoard.build(
            items
        )

        self.save(board)

        return board

    def save(self, board):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.path.with_suffix(
                self.path.suffix
                + ".tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                board,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_path.replace(
            self.path
        )

    def load(self):
        if not self.path.exists():
            return {
                "generated_at": None,
                "count": 0,
                "items": [],
                "top_overall": [],
                "top_flips": [],
                "top_holds": [],
                "top_sleepers": [],
                "by_category": {},
            }

        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return {
                "generated_at": None,
                "count": 0,
                "items": [],
                "top_overall": [],
                "top_flips": [],
                "top_holds": [],
                "top_sleepers": [],
                "by_category": {},
            }

        return (
            data
            if isinstance(
                data,
                dict,
            )
            else {}
        )