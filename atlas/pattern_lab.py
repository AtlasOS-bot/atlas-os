import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_completed_opportunities():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={
            "select": "*",
            "order": "created_at.desc",
            "limit": "50",
        },
    )

    r.raise_for_status()
    return r.json()


def already_saved(opportunity_id):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/pattern_lab",
        headers=headers(),
        params={
            "opportunity_id": f"eq.{opportunity_id}",
            "select": "id",
            "limit": "1",
        },
    )

    r.raise_for_status()
    return len(r.json()) > 0


def extract_keyword(item_name):
    words = item_name.split()

    ignore = {
        "the",
        "and",
        "new",
        "official",
        "available",
        "coming",
        "soon",
    }

    for word in words:
        cleaned = word.lower().strip(",.!?()[]")
        if len(cleaned) >= 4 and cleaned not in ignore:
            return cleaned

    return "general"


def save_pattern(item):

    if already_saved(item["id"]):
        print("Already learned:", item["item_name"])
        return

    payload = {
        "opportunity_id": item["id"],
        "brand": item["brand"],
        "keyword": extract_keyword(item["item_name"]),
        "opportunity_score": item["confidence_score"],
        "bought": None,
        "purchase_price": None,
        "sold_price": None,
        "roi_percent": None,
        "notes": "Waiting for real resale results.",
    }

    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/pattern_lab",
        headers=headers(),
        json=payload,
    )

    r.raise_for_status()

    print("Memory saved:", item["item_name"])


def main():

    items = get_completed_opportunities()

    print(f"Learning from {len(items)} opportunities")

    for item in items:
        save_pattern(item)


if __name__ == "__main__":
    main()
