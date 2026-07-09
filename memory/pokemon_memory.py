import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def recent_pokemon_items(days=30):

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={
            "brand": "eq.Pokemon",
            "select": "*",
            "order": "created_at.desc",
        },
    )

    r.raise_for_status()

    return r.json()


def pokemon_memory():

    items = recent_pokemon_items()

    memory = {
        "total_items_seen": len(items),
        "promo_count": 0,
        "exclusive_count": 0,
        "watch_count": 0,
        "buy_count": 0,
    }

    for item in items:

        reason = (item.get("atlas_reason") or "").lower()

        if "promo" in reason:
            memory["promo_count"] += 1

        if "exclusive" in reason:
            memory["exclusive_count"] += 1

        action = (item.get("recommended_action") or "").upper()

        if action == "WATCH":
            memory["watch_count"] += 1

        if action == "BUY":
            memory["buy_count"] += 1

    return memory