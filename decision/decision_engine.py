def decide(score, reprint_risk=False, pattern_count=0):
    """
    Atlas Decision Engine

    This is the final layer before Atlas tells the user
    what action to take.
    """

    confidence = "LOW"

    if score >= 90:
        confidence = "VERY HIGH"

    elif score >= 75:
        confidence = "HIGH"

    elif score >= 60:
        confidence = "MEDIUM"

    if reprint_risk:
        return {
            "action": "WATCH",
            "confidence": confidence,
            "reason":
                "Atlas detected elevated reprint risk. Wait for inventory behavior before buying."
        }

    if score >= 90:
        return {
            "action": "BUY",
            "confidence": confidence,
            "reason":
                "Strong collector signals with no major warning flags."
        }

    if score >= 70:
        return {
            "action": "STRONG WATCH",
            "confidence": confidence,
            "reason":
                "Momentum is building. Atlas recommends watching inventory closely."
        }

    return {
        "action": "WATCH",
        "confidence": confidence,
        "reason":
            "Not enough historical evidence yet."
    }