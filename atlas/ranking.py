ACTION_PRIORITY = {
    "BUY": 4,
    "STRONG WATCH": 3,
    "WATCH": 2,
    "SKIP": 1,
}

CONFIDENCE_PRIORITY = {
    "VERY HIGH": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "UNKNOWN": 0,
}

URGENCY_PRIORITY = {
    "VERY HIGH": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "UNKNOWN": 0,
}


class OpportunityRanker:

    @staticmethod
    def rank(opportunities):
        return sorted(
            opportunities,
            key=OpportunityRanker._ranking_key,
            reverse=True,
        )

    @staticmethod
    def _ranking_key(opportunity):
        analysis = opportunity.get("analysis", {})

        decision = analysis.get("decision", "WATCH")
        confidence = analysis.get("confidence", "UNKNOWN")
        urgency = analysis.get("urgency", "UNKNOWN")
        score = analysis.get("score", 0)

        roi_data = analysis.get("roi") or {}
        roi_percent = roi_data.get("roi", -999)
        profit = roi_data.get("profit", -999)

        return (
            ACTION_PRIORITY.get(decision, 0),
            roi_percent,
            profit,
            CONFIDENCE_PRIORITY.get(confidence, 0),
            URGENCY_PRIORITY.get(urgency, 0),
            score,
        )