class MissionBrief:

    @staticmethod
    def generate(item, analysis, roi=None):

        lines = []

        lines.append("=" * 40)
        lines.append("ATLAS MISSION BRIEF")
        lines.append("=" * 40)

        lines.append(f"Item: {item.get('title')}")
        lines.append(f"Brand: {item.get('brand')}")
        lines.append("")

        lines.append(f"Decision: {analysis['decision']}")
        lines.append(f"Confidence: {analysis['confidence']}")

        if roi:

            lines.append("")
            lines.append("ROI Analysis")
            lines.append(f"Retail: ${roi['retail_price']:.2f}")
            lines.append(f"Average Sold: ${roi['average_sold_price']:.2f}")
            lines.append(f"Profit: ${roi['profit']:.2f}")
            lines.append(f"ROI: {roi['roi']:.2f}%")

        lines.append("")
        lines.append("Reasons")

        for reason in analysis["reasons"]:
            lines.append(f" • {reason}")

        return "\n".join(lines)