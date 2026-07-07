import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

STRONG = {
    "limited": 18, "exclusive": 18, "pokemon center": 22, "plush": 14,
    "halloween": 22, "anniversary": 16, "collector": 16, "drop": 14,
    "coming soon": 14, "available": 10, "collection": 10,
    "disney": 14, "lego": 12, "funko": 12, "mattel": 10,
}

BAD = {
    "investor": -30, "earnings": -30, "quarter": -25, "dividend": -30,
    "board": -20, "appointment": -20, "financial": -25,
}

def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def get_unscored_raw_drops():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/raw_drops",
        headers=headers(),
        params={
            "already_scored": "eq.false",
            "select": "*",
            "limit": "20",
            "order": "detected_at.desc",
        },
    )
    r.raise_for_status()
    return r.json()

def score_drop(drop):
    text = f"{drop.get('brand','')} {drop.get('title','')} {drop.get('raw_text','')}".lower()
    score = 35
    reasons = []

    for k, v in STRONG.items():
        if k in text:
            score += v
            reasons.append(f"+ {k}")

    for k, v in BAD.items():
        if k in text:
            score += v
            reasons.append(f"- {k}")

    hype = min(100, 40 + sum(10 for k in ["new", "coming soon", "drop", "available"] if k in text))
    collector = min(100, 35 + sum(15 for k in ["pokemon", "disney", "lego", "funko", "plush", "collector"] if k in text))
    urgency = min(100, 30 + sum(20 for k in ["limited", "exclusive", "coming soon", "drop"] if k in text))
    resale = min(100, 30 + sum(15 for k in ["pokemon center", "halloween", "anniversary", "exclusive", "limited"] if k in text))

    score = max(0, min(score, 100))

    if score >= 90:
        alert, action, trip = "🔴 CRITICAL", "BUY IMMEDIATELY", "★★★★★"
    elif score >= 75:
        alert, action, trip = "🟠 HIGH", "BUY IF AVAILABLE", "★★★★☆"
    elif score >= 55:
        alert, action, trip = "🟡 MEDIUM", "BUY IF CONVENIENT", "★★★☆☆"
    else:
        alert, action, trip = "🔵 LOW", "WATCH ONLY", "★☆☆☆☆"

    reason = "Atlas signals: " + ", ".join(reasons[:8]) if reasons else "Atlas found weak resale signals."

    return score, alert, action, trip, hype, collector, urgency, resale, reason

def create_opportunity(drop, data):
    score, alert, action, trip, hype, collector, urgency, resale, reason = data

    payload = {
        "raw_drop_id": drop["id"],
        "item_name": drop["title"],
        "brand": drop["brand"],
        "category": "Auto-scored",
        "confidence_score": score,
        "alert_level": alert,
        "recommended_action": action,
        "worth_trip": trip,
        "hype_score": hype,
        "collector_score": collector,
        "urgency_score": urgency,
        "resale_signal": resale,
        "atlas_reason": reason,
        "status": "new",
    }

    r = requests.post(f"{SUPABASE_URL}/rest/v1/opportunities", json=payload, headers=headers())
    print(f"Opportunity created: {r.status_code}")
    print(r.text)
    r.raise_for_status()

def mark_raw_drop_scored(drop_id):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/raw_drops",
        json={"already_scored": True},
        headers=headers(),
        params={"id": f"eq.{drop_id}"},
    )
    r.raise_for_status()

def main():
    drops = get_unscored_raw_drops()
    print(f"Unscored raw drops found: {len(drops)}")

    for drop in drops:
        print(f"Scoring: {drop['brand']} | {drop['title']}")
        data = score_drop(drop)
        print(f"Score: {data[0]} | Alert: {data[1]} | Reason: {data[-1]}")

        if data[0] >= 55:
            create_opportunity(drop, data)
        else:
            print("Low score. No opportunity created.")

        mark_raw_drop_scored(drop["id"])

if __name__ == "__main__":
    main()
