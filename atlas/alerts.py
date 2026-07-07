import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

# SEND EVERYTHING FOR TESTING
ALERT_LEVELS_TO_SEND = [
    "🔴 CRITICAL",
    "🟠 HIGH",
    "🟡 MEDIUM",
    "🔵 LOW",
]


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
            "limit": "20",
            "order": "created_at.desc",
        },
    )
    r.raise_for_status()
    return r.json()


def send_to_discord(note):
    opp = note.get("opportunities") or {}

    if note.get("alert_level") not in ALERT_LEVELS_TO_SEND:
        print("Skipped:", note.get("alert_level"))
        return False

    title = opp.get("item_name", "Unknown")
    brand = opp.get("brand", "Unknown")
    score = opp.get("confidence_score", "N/A")
    reason = opp.get("atlas_reason", "No reasoning yet.")
    action = opp.get("recommended_action", "Review")
    ebay = opp.get("ebay_sold_comps_url", "Not available")
    source = opp.get("official_url", "Not available")

    message = f"""
🚨 **ATLAS ALERT**

**Brand:** {brand}

**Item**
{title}

━━━━━━━━━━━━━━

⭐ Score: {score}

📌 Action:
{action}

🧠 Why Atlas Flagged It

{reason}

🔗 Official Source
{source}

💰 eBay Sold Comps
{ebay}
"""

    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": message},
    )

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
            print("Sent:", note["id"])


if __name__ == "__main__":
    main()
