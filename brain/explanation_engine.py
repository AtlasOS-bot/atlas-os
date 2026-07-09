def explain(item, analysis):
    """
    Converts Atlas reasoning into a human-readable explanation.
    """

    lines = []

    lines.append(f"Recommendation: {analysis['decision']}")
    lines.append(f"Confidence: {analysis['confidence']}")
    lines.append("")

    if analysis.get("reasons"):
        lines.append("Atlas noticed:")

        for reason in analysis["reasons"]:
            lines.append(f"• {reason}")

    if analysis.get("competition_note"):
        lines.append("")
        lines.append(analysis["competition_note"])

    return "\n".join(lines)