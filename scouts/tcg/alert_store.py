import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


DEFAULT_ALERT_PATH = Path(
    os.environ.get(
        "ATLAS_TCG_ALERT_PATH",
        ".atlas_data/tcg_alerts.json",
    )
)


ACTIVE_STATUSES = {
    "NEW",
    "ACTIVE",
}


class TcgAlertStore:

    def __init__(
        self,
        path=None,
    ):
        self.path = (
            Path(path)
            if path
            else DEFAULT_ALERT_PATH
        )

    def save(
        self,
        item,
        product_key,
        alert,
    ):
        if not alert.get(
            "should_alert",
            False,
        ):
            return None

        records = self.all()

        event = alert.get(
            "event",
            "UNKNOWN",
        )

        if self.exists(
            records=records,
            product_key=product_key,
            event=event,
        ):
            return None

        strategy = (
            item.get(
                "best_strategy"
            )
            or {}
        )

        if isinstance(
            strategy,
            dict,
        ):
            strategy_name = (
                strategy.get(
                    "strategy"
                )
            )

            strategy_score = (
                strategy.get(
                    "score"
                )
            )

        else:
            strategy_name = str(
                strategy
            )

            strategy_score = None

        record = {
            "alert_id": str(
                uuid4()
            ),
            "created_at": utc_now(),
            "status": "NEW",
            "product_key": product_key,
            "title": item.get(
                "title"
            ),
            "category": (
                item.get(
                    "category"
                )
                or item.get(
                    "tcg_name"
                )
            ),
            "game_name": item.get(
                "game_name"
            ),
            "url": item.get(
                "url"
            ),
            "sku": item.get(
                "sku"
            ),
            "product_type": (
                item.get(
                    "product_type"
                )
            ),
            "event": event,
            "priority": alert.get(
                "priority"
            ),
            "score": alert.get(
                "score"
            ),
            "action": alert.get(
                "action"
            ),
            "reason": alert.get(
                "reason"
            ),
            "reasons": alert.get(
                "reasons",
                [],
            ),
            "opportunity_score": (
                item.get(
                    "opportunity_score"
                )
            ),
            "opportunity_tier": (
                item.get(
                    "opportunity_tier"
                )
            ),
            "collector_score": (
                item.get(
                    "collector_score"
                )
            ),
            "popularity_score": (
                item.get(
                    "popularity_score"
                )
            ),
            "flip_score": item.get(
                "flip_score"
            ),
            "hold_score": item.get(
                "hold_score"
            ),
            "sleeper_score": (
                item.get(
                    "sleeper_score"
                )
            ),
            "strategy": strategy_name,
            "strategy_score": (
                strategy_score
            ),
        }

        records.append(
            record
        )

        self.save_all(
            records
        )

        return record

    def exists(
        self,
        records,
        product_key,
        event,
    ):
        return any(
            record.get(
                "product_key"
            )
            == product_key
            and record.get(
                "event"
            )
            == event
            and record.get(
                "status"
            )
            in ACTIVE_STATUSES
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
            if isinstance(
                data,
                list,
            )
            else []
        )

    def active(self):
        return [
            record
            for record in self.all()
            if record.get(
                "status"
            )
            in ACTIVE_STATUSES
        ]

    def resolve(
        self,
        alert_id,
    ):
        records = self.all()
        updated = False

        for record in records:
            if record.get(
                "alert_id"
            ) != alert_id:
                continue

            record["status"] = (
                "RESOLVED"
            )

            record[
                "resolved_at"
            ] = utc_now()

            updated = True
            break

        if updated:
            self.save_all(
                records
            )

        return updated

    def save_all(self, records):
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
                records,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_path.replace(
            self.path
        )


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()