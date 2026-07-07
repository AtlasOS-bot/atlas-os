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
            "select": "*"
        },
    )

    r.raise_for_status()
    return r.json()


def notification_exists(opportunity_id):

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/notifications",
        headers=headers(),
        params={
            "opportunity_id": f"eq.{opportunity_id}",
            "select": "id",
        },
    )

    r.raise_for_status()

    return len(r.json()) > 0


def level(score):

    if score >= 95:
        return "🔴 CRITICAL"

    if score >= 85:
        return "🟠 HIGH"

    if score >= 70:
        return "🟡 MEDIUM"

    return "🔵 LOW"


def create_notification(item):

    score = item.get("confidence_score", 0)

    payload = {
        "opportunity_id": item["id"],
        "alert_level": level(score),
        "message": f"Atlas detected {item['item_name']}",
        "sent": False,
    }

    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/notifications",
        headers=headers(),
        json=payload,
    )

    r.raise_for_status()

    print("Created notification:", item["item_name"])


def main():

    for item in opportunities():

        if notification_exists(item["id"]):
            continue

        create_notification(item)


if __name__ == "__main__":
    main()
