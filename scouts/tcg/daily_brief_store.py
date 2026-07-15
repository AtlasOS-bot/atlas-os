import json
import os
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path


DEFAULT_DAILY_BRIEF_PATH = Path(
    os.environ.get(
        "ATLAS_TCG_DAILY_BRIEF_PATH",
        ".atlas_data/tcg_daily_brief.json",
    )
)


DEFAULT_HISTORY_DIRECTORY = Path(
    os.environ.get(
        "ATLAS_TCG_DAILY_HISTORY_PATH",
        ".atlas_data/tcg_daily_history",
    )
)


class TcgDailyBriefStore:

    def __init__(
        self,
        path=None,
        history_directory=None,
    ):
        self.path = (
            Path(path)
            if path
            else DEFAULT_DAILY_BRIEF_PATH
        )

        self.history_directory = (
            Path(history_directory)
            if history_directory
            else DEFAULT_HISTORY_DIRECTORY
        )

    def save(
        self,
        brief,
        preserve_history=True,
    ):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        write_json_atomic(
            path=self.path,
            payload=brief,
        )

        history_path = None

        if preserve_history:
            self.history_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            history_path = (
                self.history_directory
                / history_filename(
                    brief.get(
                        "generated_at"
                    )
                )
            )

            write_json_atomic(
                path=history_path,
                payload=brief,
            )

        return {
            "current_path": str(
                self.path
            ),
            "history_path": (
                str(history_path)
                if history_path
                else None
            ),
        }

    def load(self):
        return load_json(
            path=self.path
        )

    def history(self):
        if not self.history_directory.exists():
            return []

        files = sorted(
            self.history_directory.glob(
                "*.json"
            ),
            reverse=True,
        )

        return [
            {
                "path": str(path),
                "brief": load_json(
                    path=path
                ),
            }
            for path in files
        ]


def history_filename(
    generated_at=None,
):
    parsed = parse_datetime(
        generated_at
    )

    return (
        parsed.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        + ".json"
    )


def parse_datetime(value):
    if value:
        try:
            return datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            pass

    return datetime.now(
        timezone.utc
    )


def write_json_atomic(
    path,
    payload,
):
    temporary_path = (
        path.with_suffix(
            path.suffix
            + ".tmp"
        )
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary_path.replace(
        path
    )


def load_json(path):
    if not path.exists():
        return {}

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {}

    return (
        data
        if isinstance(
            data,
            dict,
        )
        else {}
    )