from .rules import POKEMON_RULES


def score_pokemon_item(item):
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()

    score = 40
    reasons = []

    for term in POKEMON_RULES["priority_terms"]:
        if term in text:
            score += 8
            reasons.append(f"Priority term detected: {term}")

    reprint_risk = any(term in text for term in POKEMON_RULES["watch_terms"])

    if reprint_risk:
        reasons.append("High reprint/restock risk detected — classify as WATCH, not automatic BUY.")

    if "pokemon center" in text or "pokémon center" in text:
        reasons.append("Pokémon Center source increases confidence.")

    if "exclusive" in text:
        reasons.append("Exclusive product language increases demand potential.")

    score = max(0, min(score, 100))

    if reprint_risk:
        decision = "WATCH"
    elif score >= 90:
        decision = "BUY"
    elif score >= 70:
        decision = "STRONG WATCH"
    else:
        decision = "WATCH"

    return {
        "score": score,
        "decision": decision,
        "reasons": reasons,
        "competition_note": "Competition may be high, but Atlas does not lower the score for high-competition hype drops.",
    }