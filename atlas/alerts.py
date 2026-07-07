import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


ALERT_LEVELS_TO_NOTIFY = ["🔴 CRITICAL", "🟠 HIGH"]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_opportunities_to_alert():
    endpoint = f"{SUPABASE_URL}/rest/v1/opportunities"
    params = {
        "alert_level": f"in.({','.join(ALERT_LEVELS_TO_NOTIFY)})",
        "status": "eq.new",
        "select": "*",
        "limit": "20",
        "order": "created_at.desc",
    }

    r = requests.get(endpoint, headers=headers(), params=params)
    r.raise_for_status()
    return r.json()


def notification_exists(opportunity_id):
    endpoint = f"{SUPABASE_URL}/rest/v1/notifications"
    params = {
        "opportunity_id": f"eq.{opportunity_id}",
        "select": "id",
        "limit": "1",
    }

    r = requests.get(endpoint, headers=headers(), params=params)
    r.raise_for_status()
    return len(r.json()) > 0


def create_notification(opp):
    if notification_exists(opp["id"]):
        print(f"Notification already exists: {opp['item_name']}")
        return

    endpoint = f"{SUPABASE_URL}/rest/v1/notifications"

    message = (
        f"{opp['alert_level']} ATLAS ALERT | "
        f"{opp['brand']} | "
        f"{opp['item_name']} | "
        f"Score: {opp.get('confidence_score')} | "
        f"Action: {opp.get('recommended_action')}"
    )

    payload = {
        "opportunity_id": opp["id"],
        "alert_level": opp["alert_level"],
        "message": message,
        "sent": False,
    }

    r = requests.post(endpoint, json=payload, headers=headers())
    print(f"Notification created: {r.status_code}")
    print(r.text)
    r.raise_for_status()


def main():
    opportunities = get_opportunities_to_alert()

    print(f"Opportunities needing alerts: {len(opportunities)}")

    for opp in opportunities:
        print(f"Checking alert: {opp['brand']} | {opp['item_name']}")
        create_notification(opp)


if __name__ == "__main__":
    main()
