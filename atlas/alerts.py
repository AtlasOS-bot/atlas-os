import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

ALERT_LEVELS_TO_SEND = ["🔴 CRITICAL", "🟠 HIGH"]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_unsent_notifications():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/notifications",
        headers=headers(),
        params={
            "sent": "eq.false",
            "select": "*, opportunities(*)",
            "limit": "10",
            "order": "created_at.desc",
        },
    )
    r.raise_for_status()
    return r.json()


def send_to_discord(note):
    opp = note.get("opportunities") or {}

    if note["alert_level"] not in ALERT_LEVELS_TO_SEND:
        return False

    title = opp.get("item_name", "Unknown Opportunity")
    brand = opp.get("brand", "Unknown Brand")
    score = opp.get("confidence_score", "N/A")
    action = opp.get("recommended_action", "Review")
    reason = opp.get("atlas_reason", "No Atlas reason yet.")
    ebay = opp.get("ebay_sold_comps_url", "No eBay link yet.")
    source = opp.get("official_url") or "No official link yet."

    message = f"""
🚨 **ATLAS ALERT**

**{note['alert_level']}**
**{brand}**
{title}

━━━━━━━━━━━━━━

**Atlas Score:** {score}/100
**Action:** {action}

**Why Atlas flagged it:**
{reason}

**Official Source:**
{source}

**eBay Sold Comps:**
{ebay}

━━━━━━━━━━━━━━
"""

    r = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(r.status_code)
    print(r.text)
    r.raise_for_status()
    return True


def mark_sent(notification_id):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/notifications",
        headers=headers(),
        params={"id": f"eq.{notification_id}"},
        json={"sent": True},
    )
    r.raise_for_status()


def main():
    notes = get_unsent_notifications()
    print(f"Unsent notifications: {len(notes)}")

    for note in notes:
        sent = send_to_discord(note)
        if sent:
            mark_sent(note["id"])
            print(f"Sent notification {note['id']}")


if __name__ == "__main__":
    main()
