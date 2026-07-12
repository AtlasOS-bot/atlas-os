import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scouts.pokemon.release_calendar import (
    build_release_calendar,
)


DEFAULT_RELEASE_PATH = Path(
    os.environ.get(
        "ATLAS_POKEMON_RELEASE_PATH",
        ".atlas_data/pokemon_release_calendar.json",
    )
)


class PokemonReleaseStore:

    def __init__(self, path=None):
        self.path = (
            Path(path)
            if path
            else DEFAULT_RELEASE_PATH
        )

    def save(
        self,
        items,
        today=None,
    ):
        calendar = build_release_calendar(
            items=items,
            today=today,
        )

        payload = {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "count": len(calendar),
            "releases": calendar,
        }

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return payload

    def load(self):
        if not self.path.exists():
            return {
                "generated_at": None,
                "count": 0,
                "releases": [],
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
                "releases": [],
            }

        return (
            data
            if isinstance(data, dict)
            else {
                "generated_at": None,
                "count": 0,
                "releases": [],
            }
        )