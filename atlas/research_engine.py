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


def opportunities():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={
            "research_complete": "eq.false",
            "select": "*",
        },
    )

    r.raise_for_status()
    return r.json()


def enrich(item):

    text = f"{item['brand']} {item['item_name']}".lower()

    retailer = "Unknown"
    category = "Collectible"
    release = "Unknown"
    exclusive = False

    if "pokemon" in text:
        retailer = "Pokémon Center"
        category = "Collectible Plush"
        release = "Coming Soon"
        exclusive = "pokemon center" in text

    if "lego" in text:
        retailer = "LEGO"
        category = "Building Set"

    if "disney" in text:
        retailer = "Disney Store"
        category = "Disney Merchandise"

    payload = {
        "official_source": item["brand"],
        "official_url": item.get("url"),
        "retailer": retailer,
        "release_status": release,
        "category": category,
        "exclusive": exclusive,
        "research_complete": True,
    }

    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={"id": f"eq.{item['id']}"},
        json=payload,
    )

    r.raise_for_status()

    print(f"Research complete: {item['item_name']}")


def main():

    for item in opportunities():
        enrich(item)


if __name__ == "__main__":
    main()
