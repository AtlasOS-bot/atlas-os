import os
import requests

from brain.atlas_brain import AtlasBrain


class AtlasScout:
    brand = "Unknown"
    category = "general"

    def __init__(self):
        self.supabase_url = os.environ["SUPABASE_URL"]
        self.supabase_key = os.environ["SUPABASE_SERVICE_KEY"]

    def headers(self):
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def opportunity_exists(self, item):
        official_url = item.get("url")

        if official_url:
            r = requests.get(
                f"{self.supabase_url}/rest/v1/opportunities",
                headers=self.headers(),
                params={
                    "official_url": f"eq.{official_url}",
                    "select": "id",
                    "limit": "1",
                },
            )
            r.raise_for_status()

            if len(r.json()) > 0:
                return True

        r = requests.get(
            f"{self.supabase_url}/rest/v1/opportunities",
            headers=self.headers(),
            params={
                "brand": f"eq.{item.get('brand', self.brand)}",
                "item_name": f"eq.{item.get('title')}",
                "select": "id",
                "limit": "1",
            },
        )
        r.raise_for_status()

        return len(r.json()) > 0

    def save_opportunity(self, item):
        if self.opportunity_exists(item):
            print("Duplicate skipped:", item["title"])
            return False

        analysis = AtlasBrain.analyze(
            item=item,
            category=self.category,
        )

        payload = {
            "brand": item.get("brand", self.brand),
            "item_name": item["title"],
            "official_url": item["url"],
            "confidence_score": analysis["score"],
            "recommended_action": analysis["decision"],
            "atlas_reason": analysis.get("explanation", "No explanation yet."),
            "market_signal_status": "watch",
        }

        r = requests.post(
            f"{self.supabase_url}/rest/v1/opportunities",
            headers=self.headers(),
            json=payload,
        )

        r.raise_for_status()

        print("Saved:", item["title"])
        print("Decision:", analysis["decision"])
        print("Confidence:", analysis["confidence"])

        return True

    def run(self):
        raise NotImplementedError("Each scout must define its own run method.")