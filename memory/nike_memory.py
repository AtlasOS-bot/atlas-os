import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }


def nike_memory():

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={
            "brand": "eq.Nike",
            "select": "item_name,atlas_reason",
            "limit": "500",
        },
    )

    r.raise_for_status()

    opportunities = r.json()

    memory = {
        "total_items_seen": len(opportunities),
        "hype_drop_count": 0,
        "restock_count": 0,
        "collab_count": 0,
    }

    for item in opportunities:

        text = (
            f"{item.get('item_name','')} "
            f"{item.get('atlas_reason','')}"
        ).lower()

        if "shock drop" in text or "snkrs" in text:
            memory["hype_drop_count"] += 1

        if "restock" in text:
            memory["restock_count"] += 1

        if any(
            term in text
            for term in [
                "travis",
                "off-white",
                "kobe",
                "jordan",
                "sb dunk",
            ]
        ):
            memory["collab_count"] += 1

    return memory