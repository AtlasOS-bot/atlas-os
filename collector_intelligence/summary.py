"""
Human-readable opportunity summaries. This module only formats what
is already stored on a CollectorOpportunity - it never invents a
score, price, or bullet point that wasn't supplied by the caller.
Confirmed facts, estimates, rumors, and missing information are
always labeled distinctly rather than presented uniformly.
"""


def _format_money(value):
    if value is None:
        return "Unknown"

    try:
        numeric_value = float(value)

    except (TypeError, ValueError):
        return "Unknown"

    if numeric_value == int(numeric_value):
        return f"${int(numeric_value):,}"

    return f"${numeric_value:,.2f}"


format_money = _format_money


def _format_money_with_kind(value, kind):
    formatted = _format_money(value)

    if value is None:
        return formatted

    if kind == "estimated":
        return f"{formatted} (estimated)"

    return formatted


format_money_with_kind = _format_money_with_kind


def _format_score(value):
    if value is None:
        return "Unknown"

    return f"{int(round(value))}/100"


format_score = _format_score


def _humanize(value):
    if not value:
        return None

    text = (
        value.value
        if hasattr(value, "value")
        else str(value)
    )

    return text.replace("_", " ")


humanize = _humanize


def _build_title(opportunity):
    left = (
        opportunity.franchise
        or opportunity.brand
        or "UNKNOWN"
    ).upper()

    if opportunity.collaboration_partner:
        right = (
            opportunity.collaboration_partner.upper()
        )

        suffix = (
            " PROMO"
            if opportunity.exclusive_promo
            else ""
        )

        return f"{left} × {right}{suffix}"

    if opportunity.product_name:
        return (
            f"{left} — "
            f"{opportunity.product_name.upper()}"
        )

    return left


build_title = _build_title


def summarize_opportunity(opportunity):
    """
    Returns a concise, human-readable multi-line summary of a
    CollectorOpportunity, matching Atlas's standard opportunity
    report format.
    """
    lines = [_build_title(opportunity)]

    if (
        opportunity.status
        and opportunity.status.lower() == "rumored"
    ):
        lines.append(
            "(RUMORED - not yet confirmed)"
        )

    lines.append("")
    lines.append("Recommendation:")
    lines.append(
        _humanize(opportunity.recommendation)
        or "UNKNOWN"
    )

    lines.append("")
    lines.append("Primary strategy:")
    lines.append(
        _humanize(opportunity.primary_strategy)
        or "UNKNOWN"
    )

    spend, spend_field = (
        opportunity.resolved_spend()
    )
    resale, resale_kind = (
        opportunity.resolved_resale()
    )

    lines.append("")
    lines.append("Retail or required spend:")
    lines.append(_format_money(spend))

    lines.append("")
    lines.append("Observed or estimated resale:")
    lines.append(
        _format_money_with_kind(
            resale,
            resale_kind,
        )
    )

    lines.append("")
    lines.append("Estimated gross upside:")

    profit = opportunity.estimated_profit

    if (
        profit is None
        and spend is not None
        and resale is not None
    ):
        profit = round(resale - spend, 2)

    upside_line = _format_money(profit)

    if profit is not None and (
        resale_kind == "estimated"
    ):
        upside_line += " (estimated)"

    lines.append(upside_line)

    lines.append("")
    lines.append("Collector Score:")
    lines.append(
        _format_score(
            opportunity.collector_score
        )
    )

    lines.append("")
    lines.append("Flip Score:")
    lines.append(
        _format_score(opportunity.flip_score)
    )

    lines.append("")
    lines.append("Hold Score:")
    lines.append(
        _format_score(opportunity.hold_score)
    )

    if opportunity.catalyst_signals:
        lines.append("")
        lines.append("Why it matters:")

        for signal in opportunity.catalyst_signals:
            lines.append(f"- {signal}")

    if opportunity.risks:
        lines.append("")
        lines.append("Risks:")

        for risk in opportunity.risks:
            lines.append(f"- {risk}")

    missing = _missing_high_value_fields(
        opportunity
    )

    if missing:
        lines.append("")
        lines.append("Missing information:")

        for field_name in missing:
            lines.append(f"- {field_name}")

    return "\n".join(lines)


def _missing_high_value_fields(opportunity):
    checks = [
        (
            "retail price or required spend",
            opportunity.resolved_spend()[0]
            is None,
        ),
        (
            "market or resale price",
            opportunity.resolved_resale()[0]
            is None,
        ),
        (
            "release date",
            opportunity.release_date is None,
        ),
        (
            "collector score",
            opportunity.collector_score is None,
        ),
    ]

    return [
        label
        for label, is_missing in checks
        if is_missing
    ]
