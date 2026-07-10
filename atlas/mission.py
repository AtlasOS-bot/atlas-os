class MissionBrief:

    @staticmethod
    def generate(item, analysis, roi=None):
        roi = roi if roi is not None else analysis.get("roi")
        market = analysis.get("market", {})
        market_summary = market.get("summary", {})

        lines = [
            "=" * 44,
            "ATLAS MISSION BRIEF",
            "=" * 44,
            f"Item: {item.get('title', 'Unknown item')}",
            f"Brand: {item.get('brand', 'Unknown brand')}",
            "",
            f"Decision: {analysis.get('decision', 'WATCH')}",
            f"Confidence: {analysis.get('confidence', 'UNKNOWN')}",
            f"Opportunity: {analysis.get('opportunity', 'UNKNOWN')}",
            f"Urgency: {analysis.get('urgency', 'UNKNOWN')}",
        ]

        average_price = market_summary.get("average_price")
        sold_count = market_summary.get("sold_count", 0)
        market_confidence = market_summary.get(
            "confidence",
            "UNKNOWN",
        )

        if average_price is not None:
            lines.extend([
                "",
                "MARKET INTELLIGENCE",
                f"Average Market Price: ${average_price:.2f}",
                f"Sold Listings: {sold_count}",
                f"Market Confidence: {market_confidence}",
            ])

        if roi is not None:
            lines.extend([
                "",
                "ROI ANALYSIS",
                f"Retail: ${roi['retail_price']:.2f}",
                f"Average Sold: ${roi['average_sold_price']:.2f}",
                f"Estimated Fees: ${roi['fees']:.2f}",
                f"Estimated Shipping: ${roi['shipping']:.2f}",
                f"Net Revenue: ${roi['net_revenue']:.2f}",
                f"Estimated Profit: ${roi['profit']:.2f}",
                f"Estimated ROI: {roi['roi']:.2f}%",
            ])

        lines.extend([
            "",
            "WHY ATLAS FLAGGED IT",
        ])

        for reason in analysis.get("reasons", []):
            lines.append(f"• {reason}")

        lines.extend([
            "",
            "=" * 44,
        ])

        return "\n".join(lines)