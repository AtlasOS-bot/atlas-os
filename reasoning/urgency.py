def calculate_urgency(item):
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()

    urgent_terms = [
        "shock drop",
        "exclusive access",
        "today",
        "now available",
        "limited release",
        "first come",
    ]

    score = 0

    for term in urgent_terms:
        if term in text:
            score += 1

    if score >= 3:
        return "VERY HIGH"

    if score >= 2:
        return "HIGH"

    if score >= 1:
        return "MEDIUM"

    return "LOW"