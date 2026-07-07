import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


HOT_TERMS = [
    "pokemon",
    "pokémon",
    "pokemon center",
    "plush",
    "exclusive",
    "limited",
    "halloween",
    "anniversary",
    "disney",
    "lego",
    "funko",
    "stanley",
    "costco",
    "target",
]

WEAK_TERMS = [
    "investor",
    "earnings",
    "financial",
    "conference",
    "appointment",
    "board",
]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_opportunities():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={
            "select": "*",
            "limit": "100",
            "order": "created_at.desc",
        },
    )
    r.raise_for_status()
    return r.json()


def score_market_signal(opp):
    text = f"{opp.get('brand','')} {opp.get('item_name','')} {opp.get('atlas_reason','')}".lower()

    score = 35
    reasons = []

    for term in HOT_TERMS:
        if term in text:
            score += 6
            reasons.append(term)

    for term in WEAK_TERMS:
        if term in text:
            score -= 15
            reasons.append(f"weak:{term}")

    if opp.get("ebay_sold_comps_url"):
        score += 10
        reasons.append("eBay sold-comps link ready")

    score = max(0, min(score, 100))

    if score >= 80:
        status = "strong"
    elif score >= 60:
        status = "watch"
    else:
        status = "weak"

    reason = "Market signals: " + ", ".join(reasons[:10]) if reasons else "Few free market signals detected."

    return score, status, reason


def update_opportunity(opp_id, score, status, reason):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={"id": f"eq.{opp_id}"},
        json={
            "market_signal_score": score,
            "market_signal_status": status,
            "market_signal_reason": reason,
        },
    )
    r.raise_for_status()


def main():
    opportunities = get_opportunities()
    print(f"Opportunities checked: {len(opportunities)}")

    for opp in opportunities:
        score, status, reason = score_market_signal(opp)
        update_opportunity(opp["id"], score, status, reason)
        print(f"{opp.get('brand')} | {score} | {status} | {opp.get('item_name')}")


if __name__ == "__main__":
    main()
