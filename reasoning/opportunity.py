def calculate_opportunity(score, confidence):
    if score >= 90 and confidence == "VERY HIGH":
        return "EXCEPTIONAL"

    if score >= 80:
        return "HIGH"

    if score >= 65:
        return "MEDIUM"

    return "LOW"