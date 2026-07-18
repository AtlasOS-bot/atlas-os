import os
import requests


def supabase_credentials():
    return (
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY"),
    )


def headers(service_key):
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def recent_pokemon_items(days=30):
    supabase_url, service_key = supabase_credentials()

    if not supabase_url or not service_key:
        return []

    r = requests.get(
        f"{supabase_url}/rest/v1/opportunities",
        headers=headers(service_key),
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