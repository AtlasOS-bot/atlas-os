def decide(
    score,
    reprint_risk=False,
    pattern_count=0,
    roi=None,
):
    """
    Create Atlas's final recommendation.

    Score measures product signals.
    ROI measures expected financial return.
    Reprint risk can override otherwise-positive signals.
    """

    confidence = confidence_from_score(
        score=score,
        pattern_count=pattern_count,
    )

    if roi is not None:
        profit = roi.get("profit", 0)
        roi_percent = roi.get("roi", 0)

        if profit <= 0 or roi_percent <= 0:
            return {
                "action": "SKIP",
                "confidence": confidence,
                "reason": (
                    "Estimated resale proceeds do not produce a positive "
                    "profit after fees, shipping, and purchase cost."
                ),
            }

        if reprint_risk:
            return {
                "action": "WATCH",
                "confidence": confidence,
                "reason": (
                    f"Estimated ROI is {roi_percent:.2f}%, but Atlas detected "
                    "reprint or restock risk. Wait for supply behavior and "
                    "market stability before buying."
                ),
            }

        if roi_percent >= 60 and score >= 70:
            return {
                "action": "BUY",
                "confidence": confidence,
                "reason": (
                    f"Atlas detected strong product signals and an estimated "
                    f"ROI of {roi_percent:.2f}%."
                ),
            }

        if roi_percent >= 35 and score >= 60:
            return {
                "action": "STRONG WATCH",
                "confidence": confidence,
                "reason": (
                    f"Estimated ROI is {roi_percent:.2f}%. The opportunity "
                    "looks promising, but Atlas wants stronger confirmation "
                    "before recommending an immediate purchase."
                ),
            }

        if roi_percent >= 15:
            return {
                "action": "WATCH",
                "confidence": confidence,
                "reason": (
                    f"Estimated ROI is only {roi_percent:.2f}%. There may be "
                    "profit, but the margin is not strong enough for a BUY."
                ),
            }

        return {
            "action": "SKIP",
            "confidence": confidence,
            "reason": (
                f"Estimated ROI is {roi_percent:.2f}%, which is too small "
                "after accounting for normal resale risk."
            ),
        }

    if reprint_risk:
        return {
            "action": "WATCH",
            "confidence": confidence,
            "reason": (
                "Atlas detected elevated reprint or restock risk. Wait for "
                "inventory behavior before buying."
            ),
        }

    if score >= 90:
        return {
            "action": "BUY",
            "confidence": confidence,
            "reason": (
                "Strong product signals were detected with no major warning "
                "flags, but live market pricing is still unavailable."
            ),
        }

    if score >= 70:
        return {
            "action": "STRONG WATCH",
            "confidence": confidence,
            "reason": (
                "Momentum appears strong. Atlas recommends watching price "
                "and availability closely."
            ),
        }

    return {
        "action": "WATCH",
        "confidence": confidence,
        "reason": (
            "Atlas does not have enough market evidence for a BUY decision yet."
        ),
    }


def confidence_from_score(score, pattern_count=0):
    if score >= 90 and pattern_count >= 1:
        return "VERY HIGH"

    if score >= 75:
        return "HIGH"

    if score >= 60:
        return "MEDIUM"

    return "LOW"