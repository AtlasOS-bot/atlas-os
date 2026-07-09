def calculate_confidence(evidence):
    positive = [item for item in evidence if item.get("weight", 0) > 0]
    negative = [item for item in evidence if item.get("weight", 0) < 0]

    if len(positive) >= 5 and len(negative) == 0:
        return "VERY HIGH"

    if len(positive) >= 3 and len(negative) <= 1:
        return "HIGH"

    if len(positive) >= 2:
        return "MEDIUM"

    return "LOW"