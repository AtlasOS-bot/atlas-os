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


def rows():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/pattern_lab",
        headers=headers(),
        params={
            "select": "*",
            "limit": "100",
        },
    )

    r.raise_for_status()

    return r.json()


def update(row):

    purchase = row.get("purchase_price")
    sold = row.get("sold_price")

    if purchase is None or sold is None:
        return

    shipping = row.get("shipping_cost") or 0
    fees = row.get("ebay_fees") or 0

    profit = sold - purchase - shipping - fees

    roi = round((profit / purchase) * 100, 2)

    payload = {
        "roi_percent": roi,
        "total_profit": profit,
        "learning_status": "verified",
    }

    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/pattern_lab",
        headers=headers(),
        params={"id": f"eq.{row['id']}"},
        json=payload,
    )

    r.raise_for_status()

    print(
        row["keyword"],
        roi,
    )


def main():

    for row in rows():
        update(row)


if __name__ == "__main__":
    main()
