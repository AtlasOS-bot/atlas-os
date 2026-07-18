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
    }


def nike_memory():
    supabase_url, service_key = supabase_credentials()

    if not supabase_url or not service_key:
        opportunities = []
    else:
        r = requests.get(
            f"{supabase_url}/rest/v1/opportunities",
            headers=headers(service_key),
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