class PatternScorer:

    @staticmethod
    def score(matches):
        if not matches:
            return {
                "pattern_score": 0,
                "confidence": "LOW",
                "match_count": 0,
            }

        weighted_total = 0
        total_weight = 0

        for match in matches:
            pattern = match["pattern"]
            historical_roi = pattern.get("historical_roi")

            if historical_roi is None:
                continue

            weight = max(match.get("match_strength", 1), 1)

            weighted_total += historical_roi * weight
            total_weight += weight

        if total_weight == 0:
            return {
                "pattern_score": 0,
                "confidence": "LOW",
                "match_count": len(matches),
            }

        average_roi = weighted_total / total_weight

        if average_roi >= 70:
            confidence = "VERY HIGH"
        elif average_roi >= 50:
            confidence = "HIGH"
        elif average_roi >= 30:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return {
            "pattern_score": round(average_roi, 2),
            "confidence": confidence,
            "match_count": len(matches),
        }