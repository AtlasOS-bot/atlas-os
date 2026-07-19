import os

import requests

from brain.atlas_brain import AtlasBrain
from learning.engine import LearningEngine


class AtlasScout:
    brand = "Unknown"
    category = "general"

    def __init__(self):
        self.supabase_url = os.environ["SUPABASE_URL"]
        self.supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
        self.learning_engine = LearningEngine()

    def headers(self):
        return {
            "apikey": self.supabase_key,
            "Authorization": (
                f"Bearer {self.supabase_key}"
            ),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def opportunity_exists(self, item):
        official_url = item.get("url")

        if official_url:
            response = requests.get(
                (
                    f"{self.supabase_url}"
                    "/rest/v1/opportunities"
                ),
                headers=self.headers(),
                params={
                    "official_url": (
                        f"eq.{official_url}"
                    ),
                    "select": "id",
                    "limit": "1",
                },
                timeout=20,
            )

            response.raise_for_status()

            if response.json():
                return True

        response = requests.get(
            (
                f"{self.supabase_url}"
                "/rest/v1/opportunities"
            ),
            headers=self.headers(),
            params={
                "brand": (
                    f"eq.{item.get('brand', self.brand)}"
                ),
                "item_name": (
                    f"eq.{item.get('title')}"
                ),
                "select": "id",
                "limit": "1",
            },
            timeout=20,
        )

        response.raise_for_status()

        return bool(response.json())

    def event_key_exists(self, event_key):
        response = requests.get(
            (
                f"{self.supabase_url}"
                "/rest/v1/opportunities"
            ),
            headers=self.headers(),
            params={
                "event_key": (
                    f"eq.{event_key}"
                ),
                "select": "id",
                "limit": "1",
            },
            timeout=20,
        )

        response.raise_for_status()

        return bool(response.json())

    def save_opportunity(self, item, event_key=None):
        if event_key is not None:
            if self.event_key_exists(
                event_key
            ):
                print(
                    "Duplicate skipped "
                    "(event already recorded):",
                    item["title"],
                )
                return False

        elif self.opportunity_exists(item):
            print(
                "Duplicate skipped:",
                item["title"],
            )
            return False

        analysis = AtlasBrain.analyze(
            item=item,
            category=self.category,
        )

        payload = {
            "brand": item.get(
                "brand",
                self.brand,
            ),
            "item_name": item["title"],
            "official_url": item["url"],
            "confidence_score": analysis["score"],
            "recommended_action": analysis["decision"],
            "atlas_reason": analysis.get(
                "explanation",
                "No explanation yet.",
            ),
            "market_signal_status": "watch",
        }

        if event_key is not None:
            payload["event_key"] = event_key

        response = requests.post(
            (
                f"{self.supabase_url}"
                "/rest/v1/opportunities"
            ),
            headers=self.headers(),
            json=payload,
            timeout=20,
        )

        if (
            event_key is not None
            and response.status_code == 409
        ):
            # A concurrent/near-concurrent writer already
            # inserted a row with this exact event_key; the
            # unique index rejected this one. That is the
            # correct duplicate outcome, not a failure.
            print(
                "Duplicate skipped "
                "(event already recorded, "
                "race detected):",
                item["title"],
            )
            return False

        response.raise_for_status()

        self.learning_engine.record(
            item=item,
            analysis=analysis,
        )

        print("Saved:", item["title"])
        print(
            "Decision:",
            analysis["decision"],
        )
        print(
            "Confidence:",
            analysis["confidence"],
        )

        return True

    def run(self):
        raise NotImplementedError(
            "Each scout must define its own run method."
        )