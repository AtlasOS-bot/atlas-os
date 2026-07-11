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

    def save_opportunity(self, item):
        if self.opportunity_exists(item):
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

        response = requests.post(
            (
                f"{self.supabase_url}"
                "/rest/v1/opportunities"
            ),
            headers=self.headers(),
            json=payload,
            timeout=20,
        )

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