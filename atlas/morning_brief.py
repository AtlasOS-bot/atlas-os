import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def get_top_opportunities():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={
            "select": "*",
            "order": "confidence_score.desc",
            "limit": "5",
        },
    )
    r.raise_for_status()
    return r.json()


def send_brief(items):
    if not items:
        message = "☀️ **ATLAS MORNING BRIEF**\n\nNo opportunities found yet."
    else:
        lines = ["☀️ **ATLAS MORNING BRIEF**", "", "Top Opportunities", ""]

        for i, item in enumerate(items, start=1):
            lines.append(
                f"**{i}. {item.get('brand')}**\n"
                f"{item.get('item_name')}\n"
                f"Score: {item.get('confidence_score')}/100\n"
                f"Signal: {item.get('market_signal_status', 'unknown')}\n"
                f"Action: {item.get('recommended_action')}\n"
            )

        message = "\n".join(lines)

    r = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(r.status_code)
    print(r.text)
    r.raise_for_status()


def main():
    send_brief(get_top_opportunities())


if __name__ == "__main__":
    main()
