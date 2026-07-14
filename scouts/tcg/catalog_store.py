import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CATALOG_PATH = Path(
    os.environ.get(
        "ATLAS_TCG_CATALOG_PATH",
        ".atlas_data/tcg_live_catalog.json",
    )
)


class TcgCatalogStore:

    def __init__(self, path=None):
        self.path = (
            Path(path)
            if path
            else DEFAULT_CATALOG_PATH
        )

    def upsert_many(self, items):
        catalog = self.load()

        existing_items = catalog.get(
            "items",
            [],
        )

        indexed = {
            self.product_key(item): dict(item)
            for item in existing_items
            if self.product_key(item)
        }

        created_count = 0
        updated_count = 0

        for item in items:
            key = self.product_key(item)

            if not key:
                continue

            now = utc_now()

            existing = indexed.get(key)

            if existing is None:
                record = dict(item)

                record["catalog_key"] = key
                record["first_seen_at"] = now
                record["last_seen_at"] = now
                record["scan_count"] = 1

                indexed[key] = record
                created_count += 1

            else:
                indexed[key] = self.merge_record(
                    existing=existing,
                    incoming=item,
                    observed_at=now,
                )

                updated_count += 1

        records = list(
            indexed.values()
        )

        records.sort(
            key=self.ranking_key,
            reverse=True,
        )

        payload = {
            "generated_at": utc_now(),
            "count": len(records),
            "created_this_scan": (
                created_count
            ),
            "updated_this_scan": (
                updated_count
            ),
            "items": records,
        }

        self.save(payload)

        return payload

    def load(self):
        if not self.path.exists():
            return {
                "generated_at": None,
                "count": 0,
                "created_this_scan": 0,
                "updated_this_scan": 0,
                "items": [],
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
                "created_this_scan": 0,
                "updated_this_scan": 0,
                "items": [],
            }

        if not isinstance(data, dict):
            return {
                "generated_at": None,
                "count": 0,
                "created_this_scan": 0,
                "updated_this_scan": 0,
                "items": [],
            }

        if not isinstance(
            data.get("items"),
            list,
        ):
            data["items"] = []

        return data

    def save(self, payload):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self.path.with_suffix(
            self.path.suffix + ".tmp"
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
            self.path
        )

    def all(self):
        return self.load().get(
            "items",
            [],
        )

    def by_category(self, category):
        normalized_category = (
            str(category or "")
            .strip()
            .lower()
        )

        return [
            item
            for item in self.all()
            if (
                str(
                    item.get(
                        "category",
                        "",
                    )
                )
                .strip()
                .lower()
                == normalized_category
            )
        ]

    def top(
        self,
        limit=20,
        category=None,
    ):
        items = (
            self.by_category(category)
            if category
            else self.all()
        )

        return sorted(
            items,
            key=self.ranking_key,
            reverse=True,
        )[:limit]

    @staticmethod
    def merge_record(
        existing,
        incoming,
        observed_at,
    ):
        merged = dict(existing)

        protected_fields = {
            "catalog_key",
            "first_seen_at",
        }

        for key, value in incoming.items():
            if key in protected_fields:
                continue

            if value in (
                None,
                "",
                [],
                {},
            ):
                continue

            current = merged.get(key)

            if (
                key == "description"
                and current
                and len(str(current))
                > len(str(value))
            ):
                continue

            if (
                key == "sources"
                and isinstance(value, list)
            ):
                old_sources = (
                    current
                    if isinstance(
                        current,
                        list,
                    )
                    else []
                )

                merged[key] = list(
                    dict.fromkeys(
                        old_sources + value
                    )
                )

                continue

            if (
                key == "set_codes"
                and isinstance(value, list)
            ):
                old_codes = (
                    current
                    if isinstance(
                        current,
                        list,
                    )
                    else []
                )

                merged[key] = list(
                    dict.fromkeys(
                        old_codes + value
                    )
                )

                continue

            merged[key] = value

        merged["last_seen_at"] = (
            observed_at
        )

        merged["scan_count"] = (
            int(
                existing.get(
                    "scan_count",
                    0,
                )
                or 0
            )
            + 1
        )

        return merged

    @staticmethod
    def product_key(item):
        category = normalize_value(
            item.get("category")
            or item.get("tcg_name")
            or "tcg"
        )

        sku = normalize_code(
            item.get("sku")
        )

        if sku:
            return (
                f"{category}:sku:{sku}"
            )

        set_codes = item.get(
            "set_codes"
        ) or []

        if isinstance(
            set_codes,
            str,
        ):
            set_codes = [
                set_codes,
            ]

        normalized_codes = sorted({
            normalize_code(code)
            for code in set_codes
            if normalize_code(code)
        })

        product_type = normalize_value(
            item.get("product_type")
            or "other"
        )

        if normalized_codes:
            return (
                f"{category}:codes:"
                f"{'|'.join(normalized_codes)}:"
                f"{product_type}"
            )

        url = normalize_url(
            item.get("url")
        )

        if url:
            return (
                f"{category}:url:{url}"
            )

        title = normalize_title(
            item.get("title")
        )

        if title:
            return (
                f"{category}:title:{title}"
            )

        return None

    @staticmethod
    def ranking_key(item):
        strategy = (
            item.get("best_strategy")
            or {}
        )

        strategy_score = (
            strategy.get("score", 0)
            if isinstance(
                strategy,
                dict,
            )
            else 0
        )

        return (
            number_value(
                strategy_score
            ),
            number_value(
                item.get(
                    "collector_score"
                )
            ),
            number_value(
                item.get(
                    "hold_score"
                )
            ),
            number_value(
                item.get(
                    "flip_score"
                )
            ),
            number_value(
                item.get(
                    "popularity_score"
                )
            ),
        )


def normalize_value(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def normalize_code(value):
    normalized = (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "-")
    )

    normalized = re.sub(
        r"-+",
        "-",
        normalized,
    )

    return normalized


def normalize_url(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .split("#")[0]
        .rstrip("/")
    )


def normalize_title(value):
    normalized = (
        str(value or "")
        .strip()
        .lower()
    )

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split()
    )


def number_value(value):
    try:
        return float(
            value or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()