import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)


DEFAULT_STATE_PATH = Path(
    os.environ.get(
        "ATLAS_TCG_STATE_PATH",
        ".atlas_data/tcg_product_states.json",
    )
)


class TcgStateTracker:

    def __init__(
        self,
        path=None,
    ):
        self.path = (
            Path(path)
            if path
            else DEFAULT_STATE_PATH
        )

    def observe_many(self, items):
        states = self.load()

        observations = []

        for item in items:
            product_key = (
                TcgCatalogStore.product_key(
                    item
                )
            )

            if not product_key:
                continue

            current = self.snapshot(
                item
            )

            previous = states.get(
                product_key
            )

            changes = self.compare(
                previous=previous,
                current=current,
            )

            observation = {
                "product_key": (
                    product_key
                ),
                "title": item.get(
                    "title"
                ),
                "category": item.get(
                    "category"
                    or item.get(
                        "tcg_name"
                    )
                ),
                "changes": changes,
                "has_change": bool(
                    changes
                ),
                "previous": previous,
                "current": current,
            }

            observations.append(
                observation
            )

            states[product_key] = (
                current
            )

        self.save(states)

        return observations

    def snapshot(self, item):
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
                number_value(
                    strategy.get(
                        "score"
                    )
                )
            )

        else:
            strategy_name = str(
                strategy
            )

            strategy_score = 0

        return {
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
            "url": item.get(
                "url"
            ),
            "sku": item.get(
                "sku"
            ),
            "retail_price": (
                price_value(
                    item.get(
                        "retail_price"
                    )
                )
            ),
            "currency": item.get(
                "currency"
            ),
            "availability": (
                normalize_availability(
                    item.get(
                        "availability"
                    )
                )
            ),
            "release_date": item.get(
                "release_date"
            ),
            "sources": normalized_list(
                item.get(
                    "sources"
                )
            ),
            "collector_score": (
                number_value(
                    item.get(
                        "collector_score"
                    )
                )
            ),
            "popularity_score": (
                number_value(
                    item.get(
                        "popularity_score"
                    )
                )
            ),
            "flip_score": number_value(
                item.get(
                    "flip_score"
                )
            ),
            "hold_score": number_value(
                item.get(
                    "hold_score"
                )
            ),
            "sleeper_score": (
                number_value(
                    item.get(
                        "sleeper_score"
                    )
                )
            ),
            "opportunity_score": (
                number_value(
                    item.get(
                        "opportunity_score"
                    )
                )
            ),
            "opportunity_tier": (
                item.get(
                    "opportunity_tier"
                )
            ),
            "strategy": strategy_name,
            "strategy_score": (
                strategy_score
            ),
            "observed_at": utc_now(),
        }

    def compare(
        self,
        previous,
        current,
    ):
        if previous is None:
            return [
                {
                    "event": (
                        "NEW_PRODUCT"
                    ),
                    "importance": "HIGH",
                    "reason": (
                        "Atlas has not observed "
                        "this TCG product before."
                    ),
                }
            ]

        changes = []

        previous_availability = (
            previous.get(
                "availability"
            )
        )

        current_availability = (
            current.get(
                "availability"
            )
        )

        if (
            is_unavailable(
                previous_availability
            )
            and is_available(
                current_availability
            )
        ):
            changes.append({
                "event": "RESTOCK",
                "importance": (
                    "CRITICAL"
                ),
                "reason": (
                    "Availability changed from "
                    "unavailable to available."
                ),
            })

        elif (
            is_available(
                previous_availability
            )
            and is_unavailable(
                current_availability
            )
        ):
            changes.append({
                "event": "SOLD_OUT",
                "importance": "HIGH",
                "reason": (
                    "Availability changed from "
                    "available to unavailable."
                ),
            })

        previous_price = (
            previous.get(
                "retail_price"
            )
        )

        current_price = (
            current.get(
                "retail_price"
            )
        )

        if (
            previous_price is not None
            and current_price is not None
        ):
            difference = round(
                current_price
                - previous_price,
                2,
            )

            if difference < 0:
                changes.append({
                    "event": (
                        "PRICE_DROP"
                    ),
                    "importance": "HIGH",
                    "reason": (
                        f"Retail price fell from "
                        f"${previous_price:.2f} "
                        f"to ${current_price:.2f}."
                    ),
                    "previous_value": (
                        previous_price
                    ),
                    "current_value": (
                        current_price
                    ),
                })

            elif difference > 0:
                changes.append({
                    "event": (
                        "PRICE_INCREASE"
                    ),
                    "importance": (
                        "MEDIUM"
                    ),
                    "reason": (
                        f"Retail price rose from "
                        f"${previous_price:.2f} "
                        f"to ${current_price:.2f}."
                    ),
                    "previous_value": (
                        previous_price
                    ),
                    "current_value": (
                        current_price
                    ),
                })

        previous_sources = set(
            normalized_list(
                previous.get(
                    "sources"
                )
            )
        )

        current_sources = set(
            normalized_list(
                current.get(
                    "sources"
                )
            )
        )

        new_sources = (
            current_sources
            - previous_sources
        )

        if new_sources:
            changes.append({
                "event": (
                    "NEW_CONFIRMATION"
                ),
                "importance": "MEDIUM",
                "reason": (
                    "New official source "
                    "confirmation: "
                    + ", ".join(
                        sorted(
                            new_sources
                        )
                    )
                ),
                "new_sources": sorted(
                    new_sources
                ),
            })

        previous_strategy_score = (
            number_value(
                previous.get(
                    "strategy_score"
                )
            )
        )

        current_strategy_score = (
            number_value(
                current.get(
                    "strategy_score"
                )
            )
        )

        strategy_change = round(
            current_strategy_score
            - previous_strategy_score,
            2,
        )

        if strategy_change >= 10:
            changes.append({
                "event": (
                    "STRATEGY_UPGRADE"
                ),
                "importance": "HIGH",
                "reason": (
                    "Best-strategy score rose "
                    f"from "
                    f"{previous_strategy_score:.0f} "
                    f"to "
                    f"{current_strategy_score:.0f}."
                ),
                "previous_value": (
                    previous_strategy_score
                ),
                "current_value": (
                    current_strategy_score
                ),
            })

        previous_tier = (
            previous.get(
                "opportunity_tier"
            )
        )

        current_tier = (
            current.get(
                "opportunity_tier"
            )
        )

        if tier_improved(
            previous_tier,
            current_tier,
        ):
            changes.append({
                "event": (
                    "TIER_UPGRADE"
                ),
                "importance": (
                    tier_importance(
                        current_tier
                    )
                ),
                "reason": (
                    "Opportunity tier improved "
                    f"from "
                    f"{previous_tier or 'UNKNOWN'} "
                    f"to "
                    f"{current_tier}."
                ),
                "previous_value": (
                    previous_tier
                ),
                "current_value": (
                    current_tier
                ),
            })

        return changes

    def load(self):
        if not self.path.exists():
            return {}

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
            return {}

        return (
            data
            if isinstance(
                data,
                dict,
            )
            else {}
        )

    def save(self, states):
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
                states,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_path.replace(
            self.path
        )


TIER_ORDER = {
    "WATCH": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def tier_improved(
    previous,
    current,
):
    if not current:
        return False

    return (
        TIER_ORDER.get(
            current,
            0,
        )
        > TIER_ORDER.get(
            previous,
            0,
        )
    )


def tier_importance(tier):
    if tier == "CRITICAL":
        return "CRITICAL"

    if tier == "HIGH":
        return "HIGH"

    return "MEDIUM"


def is_available(value):
    return value in {
        "instock",
        "available",
        "preorder",
        "preorderonly",
        "availablefororder",
    }


def is_unavailable(value):
    return value in {
        "soldout",
        "outofstock",
        "unavailable",
        "discontinued",
        "preorderclosed",
    }


def normalize_availability(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


def normalized_list(value):
    if isinstance(
        value,
        list,
    ):
        candidates = value

    elif value:
        candidates = [
            value,
        ]

    else:
        candidates = []

    return list(
        dict.fromkeys(
            str(candidate)
            for candidate in candidates
            if candidate
        )
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


def price_value(value):
    if value is None:
        return None

    try:
        return round(
            float(value),
            2,
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()