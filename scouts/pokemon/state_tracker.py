import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scouts.pokemon.identity import (
    canonical_product_key,
)


DEFAULT_STATE_PATH = Path(
    os.environ.get(
        "ATLAS_POKEMON_STATE_PATH",
        ".atlas_data/pokemon_product_states.json",
    )
)


class PokemonStateTracker:

    def __init__(self, path=None):
        self.path = (
            Path(path)
            if path
            else DEFAULT_STATE_PATH
        )

    def observe(self, item):
        states = self._load()

        product_key = (
            canonical_product_key(item)
            or item.get("url")
            or item.get("title", "").lower()
        )

        current_state = self._snapshot(
            item
        )

        previous_state = states.get(
            product_key
        )

        event = self._compare(
            previous=previous_state,
            current=current_state,
        )

        states[product_key] = current_state

        self._save(states)

        return {
            "product_key": product_key,
            "event": event["event"],
            "importance": event["importance"],
            "reason": event["reason"],
            "previous": previous_state,
            "current": current_state,
        }

    def _snapshot(self, item):
        return {
            "title": item.get("title"),
            "url": item.get("url"),
            "sku": item.get("sku"),
            "retail_price": self._price(
                item.get("retail_price")
            ),
            "availability": self._availability(
                item.get("availability")
            ),
            "release_date": item.get(
                "release_date"
            ),
            "sources": item.get(
                "sources",
                [],
            ),
            "observed_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    def _compare(
        self,
        previous,
        current,
    ):
        if previous is None:
            return {
                "event": "NEW_PRODUCT",
                "importance": "HIGH",
                "reason": (
                    "Atlas has not observed this "
                    "product before."
                ),
            }

        previous_availability = (
            previous.get("availability")
        )

        current_availability = (
            current.get("availability")
        )

        if (
            self._is_unavailable(
                previous_availability
            )
            and self._is_available(
                current_availability
            )
        ):
            return {
                "event": "RESTOCK",
                "importance": "VERY HIGH",
                "reason": (
                    "The product changed from "
                    "unavailable to available."
                ),
            }

        if (
            self._is_available(
                previous_availability
            )
            and self._is_unavailable(
                current_availability
            )
        ):
            return {
                "event": "SOLD_OUT",
                "importance": "HIGH",
                "reason": (
                    "The product changed from "
                    "available to unavailable."
                ),
            }

        previous_price = previous.get(
            "retail_price"
        )

        current_price = current.get(
            "retail_price"
        )

        if (
            previous_price is not None
            and current_price is not None
        ):
            price_change = round(
                current_price
                - previous_price,
                2,
            )

            if price_change < 0:
                return {
                    "event": "PRICE_DROP",
                    "importance": "HIGH",
                    "reason": (
                        f"Official retail price fell "
                        f"from ${previous_price:.2f} "
                        f"to ${current_price:.2f}."
                    ),
                }

            if price_change > 0:
                return {
                    "event": "PRICE_INCREASE",
                    "importance": "MEDIUM",
                    "reason": (
                        f"Official retail price rose "
                        f"from ${previous_price:.2f} "
                        f"to ${current_price:.2f}."
                    ),
                }

        previous_sources = set(
            previous.get("sources")
            or []
        )

        current_sources = set(
            current.get("sources")
            or []
        )

        added_sources = (
            current_sources
            - previous_sources
        )

        if added_sources:
            return {
                "event": "NEW_CONFIRMATION",
                "importance": "MEDIUM",
                "reason": (
                    "Additional official source "
                    "confirmation detected: "
                    + ", ".join(
                        sorted(added_sources)
                    )
                ),
            }

        return {
            "event": "NO_CHANGE",
            "importance": "LOW",
            "reason": (
                "No meaningful product-state "
                "change was detected."
            ),
        }

    def _load(self):
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
            if isinstance(data, dict)
            else {}
        )

    def _save(self, states):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                states,
                file,
                indent=2,
                ensure_ascii=False,
            )

    @staticmethod
    def _price(value):
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

    @staticmethod
    def _availability(value):
        if not value:
            return "unknown"

        return (
            str(value)
            .strip()
            .lower()
            .replace("_", "")
            .replace("-", "")
            .replace(" ", "")
        )

    @staticmethod
    def _is_available(value):
        return value in {
            "instock",
            "available",
            "preorder",
            "preorderonly",
        }

    @staticmethod
    def _is_unavailable(value):
        return value in {
            "soldout",
            "outofstock",
            "unavailable",
            "discontinued",
        }