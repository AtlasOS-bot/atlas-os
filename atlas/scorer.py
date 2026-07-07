import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


GOOD_KEYWORDS = {
    "limited": 18,
    "exclusive": 18,
    "coming soon": 15,
    "pokemon center": 20,
    "plush": 12,
    "anniversary": 12,
    "collection": 10,
    "halloween": 20,
    "holiday": 12,
    "disney": 12,
    "lego": 10,
    "funko": 10,
    "collector": 15,
    "drop": 12,
    "available": 8,
}

BAD_KEYWORDS = {
    "investor": -25,
    "earnings": -25,
    "quarter": -20,
    "dividend": -25,
    "conference": -15,
    "appointment": -15,
    "financial": -20,
    "board": -15,
}


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_unscored_raw_drops():
    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"
    params = {
        "already_scored": "eq.false",
        "select": "*",
        "limit": "20",
        "order": "detected_at.desc",
    }

    r = requests.get(endpoint, headers=headers(), params=params)
    r.raise_for_status()
    return r.json()


def score_drop(drop):
    text = f"{drop.get('brand','')} {drop.get('title','')} {drop.get('raw_text','')}".lower()

    score = 35

    for keyword, points in GOOD_KEYWORDS.items():
        if keyword in text:
            score += points

    for keyword, points in BAD_KEYWORDS.items():
        if keyword in text:
            score += points

    score = max(0, min(score, 100))

    if score >= 90:
        alert = "🔴 CRITICAL"
        action = "BUY IMMEDIATELY"
        worth_trip = "★★★★★"
    elif score >= 75:
        alert = "🟠 HIGH"
        action = "BUY IF AVAILABLE"
        worth_trip = "★★★★☆"
    elif score >= 55:
        alert = "🟡 MEDIUM"
        action = "BUY IF CONVENIENT"
        worth_trip = "★★★☆☆"
    else:
        alert = "🔵 LOW"
        action = "WATCH ONLY"
        worth_trip = "★☆☆☆☆"

    return score, alert, action, worth_trip


def create_opportunity(drop, score, alert, action, worth_trip):
    endpoint = f"{SUPABASE_URL}/rest/v1/opportunities"

    payload = {
        "raw_drop_id": drop["id"],
        "item_name": drop["title"],
        "brand": drop["brand"],
        "category": "Auto-scored",
        "confidence_score": score,
        "alert_level": alert,
        "recommended_action": action,
        "worth_trip": worth_trip,
        "status": "new",
    }

    r = requests.post(endpoint, json=payload, headers=headers())
    print(f"Opportunity created: {r.status_code}")
    print(r.text)
    r.raise_for_status()


def mark_raw_drop_scored(drop_id):
    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"
    params = {"id": f"eq.{drop_id}"}
    payload = {"already_scored": True}

    r = requests.patch(endpoint, json=payload, headers=headers(), params=params)
    r.raise_for_status()


def main():
    drops = get_unscored_raw_drops()

    print(f"Unscored raw drops found: {len(drops)}")

    for drop in drops:
        print(f"Scoring: {drop['brand']} | {drop['title']}")

        score, alert, action, worth_trip = score_drop(drop)

        print(f"Score: {score}")
        print(f"Alert: {alert}")

        if score >= 55:
            create_opportunity(drop, score, alert, action, worth_trip)
        else:
            print("Low score. No opportunity created.")

        mark_raw_drop_scored(drop["id"])


if __name__ == "__main__":
    main()
