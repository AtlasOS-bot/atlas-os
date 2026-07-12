import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from scouts.pokemon.identity import (
    canonical_product_key,
)


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

        product_key = (
            canonical_product_key(item)
            or item.get("url")
            or item.get("title", "").lower()
        )

        event = alert.get(
            "event",
            "UNKNOWN",
        )

        if self.alert_exists(
            records=records,
            product_key=product_key,
            event=event,
        ):
            return None

        record = {
            "alert_id": str(uuid4()),
            "product_key": product_key,
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "title": item.get("title"),
            "url": item.get("url"),
            "sku": item.get("sku"),
            "product_type": item.get(
                "product_type"
            ),
            "event": event,
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
            "consensus_score": item.get(
                "consensus_score"
            ),
            "release_urgency": (
                item.get("release_urgency")
                or {}
            ).get("level"),
            "reasons": alert.get(
                "reasons",
                [],
            ),
            "status": "NEW",
        }

        records.append(record)

        self._save(records)

        return record

    def alert_exists(
        self,
        records,
        product_key,
        event,
    ):
        return any(
            record.get("product_key")
            == product_key
            and record.get("event")
            == event
            and record.get("status")
            in {
                "NEW",
                "ACTIVE",
            }
            for record in records
        )

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

    def active(self):
        return [
            record
            for record in self.all()
            if record.get("status")
            in {
                "NEW",
                "ACTIVE",
            }
        ]

    def mark_resolved(
        self,
        alert_id,
    ):
        records = self.all()
        updated = False

        for record in records:
            if (
                record.get("alert_id")
                == alert_id
            ):
                record["status"] = "RESOLVED"
                record["resolved_at"] = (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                )
                updated = True
                break

        if updated:
            self._save(records)

        return updated

    def _save(self, records):
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