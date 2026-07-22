"""
Atlas v21 - Module 4: human-readable summary for finalized opportunities.

Pure formatter - never invents data, always labels confirmed facts,
reported facts, estimates, rumors, unresolved conflicts, and stale
information as such.
"""

from collector_intelligence.summary import (
    build_title,
    format_money,
    humanize,
)


def _price_label(opportunity):
    if opportunity.recent_sold_price is not None:
        return "sold price", opportunity.recent_sold_price
    if opportunity.current_market_price is not None:
        return "current market price", opportunity.current_market_price
    if opportunity.estimated_market_price is not None:
        return "estimated price", opportunity.estimated_market_price
    return None, None


def _resale_refers_to_complete_set(opportunity):
    return any("complete set" in risk.lower() for risk in opportunity.risks)


def summarize_finalized_opportunity(finalized):
    opportunity = finalized.opportunity
    evaluation = finalized.evaluation

    lines = [build_title(opportunity)]

    if (opportunity.status or "").strip().lower() == "rumored":
        lines.append("(RUMORED - not yet confirmed)")

    lines.append("")
    lines.append("Recommendation:")
    lines.append(humanize(evaluation.recommendation).upper())

    lines.append("")
    lines.append("Strategy:")
    lines.append(humanize(evaluation.primary_strategy).upper())

    spend, spend_field = opportunity.resolved_spend()
    lines.append("")
    lines.append("Required spend:")
    lines.append(
        f"Approximately {format_money(spend)}"
        if spend is not None else "Unknown"
    )

    price_label, price_value = _price_label(opportunity)
    lines.append("")
    lines.append("Reported resale:")

    if price_value is not None:
        scope_note = (
            " for a complete set"
            if _resale_refers_to_complete_set(opportunity) else ""
        )
        certainty = (
            "Approximately"
            if price_label != "sold price" else "Reportedly"
        )
        lines.append(f"{certainty} {format_money(price_value)}{scope_note}")
    else:
        lines.append("Unknown")

    if _resale_refers_to_complete_set(opportunity):
        lines.append("")
        lines.append("Important:")
        lines.append(
            "The available resale evidence applies to a complete set, not "
            "one individual unit."
        )

    if opportunity.status:
        lines.append("")
        lines.append("Current status:")
        lines.append(humanize(opportunity.status).title())

    lines.append("")
    lines.append("Sources:")
    lines.append(f"{len(finalized.accepted_sources)} accepted")
    lines.append(f"{len(finalized.rejected_sources)} rejected")

    lines.append("")
    lines.append("Evidence quality:")
    if finalized.finalization_confidence >= 70:
        lines.append("Strong")
    elif finalized.finalization_confidence >= 40:
        lines.append("Moderate")
    else:
        lines.append("Weak")

    if evaluation.positive_factors:
        lines.append("")
        lines.append("Why Atlas is interested:")
        for factor in evaluation.positive_factors[:6]:
            lines.append(f"- {factor}")

    caution_items = list(evaluation.negative_factors[:4])
    if finalized.conflicts:
        for conflict in finalized.conflicts:
            if conflict.requires_manual_review:
                caution_items.append(conflict.explanation)

    if caution_items:
        lines.append("")
        lines.append("Why Atlas is cautious:")
        seen = set()
        for item in caution_items:
            if item not in seen:
                seen.add(item)
                lines.append(f"- {item}")

    if evaluation.missing_information:
        lines.append("")
        lines.append("Missing information:")
        for item in evaluation.missing_information:
            lines.append(f"- {humanize(item)}")

    if finalized.requires_manual_review:
        lines.append("")
        lines.append("Manual review:")
        if finalized.manual_review_reasons:
            lines.append(finalized.manual_review_reasons[0])
        else:
            lines.append("Required before treating this as a confirmed opportunity.")

        if evaluation.recommendation != "CRITICAL_BUY":
            lines.append(
                "Required before treating this as a CRITICAL BUY."
            )

    return "\n".join(lines)
