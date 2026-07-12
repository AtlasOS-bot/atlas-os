import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


DEFAULT_ALERT_PATH = Path(
    os.environ.get(
        "ATLAS_POKEMON_ALERT_PATH",
        ".atlas_data/pokemon_alerts.json",
    )
)


class PokemonAlertStore:

    def __init__(self, path=None):
        self.path = (
            Path(path)
            if path
            else DEFAULT_ALERT_PATH
        )

    def save(self, item, alert):
        if not alert.get(
            "should_alert",
            False,
        ):
            return None

        records = self.all()

        record = {
            "alert_id": str(uuid4()),
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "title": item.get("title"),
            "url": item.get("url"),
            "sku": item.get("sku"),
            "product_type": item.get(
                "product_type"
            ),
            "event": alert.get("event"),
            "priority": alert.get(
                "priority"
            ),
            "score": alert.get("score"),
            "action": alert.get("action"),
            "reason": (
                item.get("state_change")
                or {}
            ).get("reason"),
            "best_strategy": (
                item.get("best_strategy")
                or {}
            ).get("strategy"),
            "flip_score": item.get(
                "flip_score"
            ),
            "hold_score": item.get(
                "hold_score"
            ),
            "sleeper_score": item.get(
                "sleeper_score"
            ),
            "collector_score": item.get(
                "collector_score"
            ),
            "popularity_score": item.get(
                "popularity_score"
            ),
            "reasons": alert.get(
                "reasons",
                [],
            ),
        }

        records.append(record)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                records,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return record

    def all(self):
        if not self.path.exists():
            return []

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
            return []

        return (
            data
            if isinstance(data, list)
            else []
        )