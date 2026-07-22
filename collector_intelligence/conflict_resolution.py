"""
Atlas v21 - Module 4: conflict detection and resolution primitives.

Given a set of EvidenceRecord candidates for one field, decides which
value wins, marks every record accepted/rejected with a reason, and
(when the candidates disagree) produces a FieldConflict describing
what disagreed, how it was resolved, and whether a human needs to
look at it. No field-specific hardcoding beyond the priority tables in
FinalizationConfig - the same resolve_field() runs for every field.
"""

from collector_intelligence.aggregation_models import FieldConflict, MergeDecision
from collector_intelligence.normalize import normalize_text


# Identity fields where "materially different, non-rumored, comparable
# authority" values must be flagged for manual review rather than
# silently picking one - getting the wrong product identity is the
# worst kind of silent failure.
IDENTITY_CRITICAL_FIELDS = {
    "product_name", "brand", "franchise", "collaboration_partner", "retailer",
}

PRICE_FIELDS = {
    "retail_price", "required_spend", "recent_sold_price",
    "current_market_price", "estimated_market_price",
}


def priority_rank(field_name, source_type, config):
    order = config.field_source_priority.get(field_name)

    if order and source_type in order:
        return len(order) - order.index(source_type)

    return config.source_type_weights.get(source_type, 0)


def _certainty_rank(record):
    if record.rumored:
        return 0
    if record.estimated:
        return 1
    if record.confirmed:
        return 2
    return 1


def _rank_key(record, field_name, config):
    return (
        priority_rank(field_name, record.source_type, config),
        _certainty_rank(record),
        record.confidence,
    )


def _value_key(record):
    return record.normalized_value if record.normalized_value is not None else record.proposed_value


def _is_more_specific(candidate, baseline):
    """
    True if `candidate` is a strict textual extension of `baseline`
    (same normalized words plus more) - used so a vague identity value
    from a lower-priority-but-still-credible source never silently
    replaces a more specific one, and so a specific value can win over
    a vaguer higher-priority one.
    """
    norm_candidate = normalize_text(candidate)
    norm_baseline = normalize_text(baseline)

    if not norm_candidate or not norm_baseline:
        return False

    return norm_baseline in norm_candidate and norm_candidate != norm_baseline


def _price_severity(values, config):
    numeric = [v for v in values if isinstance(v, (int, float))]

    if len(numeric) < 2:
        return "LOW"

    low, high = min(numeric), max(numeric)

    if low <= 0:
        return "MEDIUM"

    percent_diff = ((high - low) / low) * 100
    thresholds = config.conflict_severity_thresholds

    if percent_diff >= thresholds.get("price_critical_percent", 200.0):
        return "CRITICAL"
    if percent_diff >= thresholds.get("price_high_percent", 50.0):
        return "HIGH"
    if percent_diff >= thresholds.get("price_material_percent", 15.0):
        return "MEDIUM"

    return "LOW"


def resolve_field(field_name, records, config):
    """
    Mutates `records` in place (accepted/rejection_reason), and
    returns (chosen_value, FieldConflict | None, MergeDecision | None).
    `records` must all be candidates for the same field_name.
    """
    if not records:
        return None, None, None

    ranked = sorted(records, key=lambda r: _rank_key(r, field_name, config), reverse=True)
    best = ranked[0]

    # Identity fields: prefer a more specific value over a vaguer one
    # from a non-rumored source, even if that source ranks lower.
    if field_name in IDENTITY_CRITICAL_FIELDS:
        for candidate in ranked[1:]:
            if candidate.rumored:
                continue
            if _is_more_specific(candidate.proposed_value, best.proposed_value):
                best = candidate
                break

    distinct = {}
    for record in records:
        distinct.setdefault(_value_key(record), []).append(record)

    chosen_key = _value_key(best)

    if len(distinct) == 1:
        for record in records:
            record.accepted = True
        return best.proposed_value, None, MergeDecision(
            field_name=field_name,
            chosen_value=best.proposed_value,
            chosen_source=best.source_name or best.source_type,
            rule_applied="single consistent value",
            alternative_values=[],
        )

    for record in records:
        if _value_key(record) == chosen_key:
            record.accepted = True
        else:
            record.accepted = False
            record.rejection_reason = (
                f"weaker evidence than {best.source_name or best.source_type} "
                f"for {field_name}"
            )

    severity, requires_review, explanation = _classify_conflict(
        field_name, ranked, best, distinct, config
    )

    conflict = FieldConflict(
        field_name=field_name,
        competing_values=list(distinct.keys()),
        evidence_references=[
            r.source_name or r.source_type or "unknown source" for r in records
        ],
        severity=severity,
        resolution=(
            f"Selected {best.proposed_value!r} from "
            f"{best.source_name or best.source_type}"
        ),
        auto_resolved=not requires_review,
        requires_manual_review=requires_review,
        explanation=explanation,
    )

    decision = MergeDecision(
        field_name=field_name,
        chosen_value=best.proposed_value,
        chosen_source=best.source_name or best.source_type,
        rule_applied=f"highest-priority source for {field_name}",
        alternative_values=[v for v in distinct if v != chosen_key],
    )

    return best.proposed_value, conflict, decision


def _classify_conflict(field_name, ranked, best, distinct, config):
    top_rank = _rank_key(best, field_name, config)[0]

    comparable_top = [
        r for r in ranked
        if _rank_key(r, field_name, config)[0] == top_rank and not r.rumored
    ]
    comparable_disagree = len({_value_key(r) for r in comparable_top}) > 1

    if field_name in IDENTITY_CRITICAL_FIELDS:
        materially_different = any(
            not _is_more_specific(a, b) and not _is_more_specific(b, a) and a != b
            for a in distinct for b in distinct if a != b
        )

        if comparable_disagree and materially_different:
            return (
                "CRITICAL",
                True,
                f"Multiple comparably authoritative, non-rumored sources "
                f"disagree on {field_name} with no specificity relationship "
                f"between the values - this must be reviewed before treating "
                f"them as the same product.",
            )

        return (
            "LOW",
            False,
            f"{field_name} values differ only in specificity - the more "
            f"specific/authoritative value was kept.",
        )

    if field_name in PRICE_FIELDS:
        severity = _price_severity(list(distinct.keys()), config)

        requires_review = severity in {"HIGH", "CRITICAL"} and comparable_disagree

        return (
            severity,
            requires_review,
            f"{field_name} candidates differ; the highest-priority source's "
            f"value was kept. {'Comparable-authority sources disagree - '
            'review recommended.' if requires_review else ''}",
        )

    if field_name == "status":
        return (
            "INFO",
            False,
            "Status evolved across sources; the most recent evidence from "
            "the most credible tier was kept, and all observations are "
            "preserved in status history.",
        )

    if comparable_disagree:
        return (
            "MEDIUM",
            True,
            f"Comparably authoritative sources disagree on {field_name}.",
        )

    return (
        "LOW",
        False,
        f"Lower-priority source(s) disagreed with the accepted value for "
        f"{field_name}; the higher-priority source's value was kept.",
    )
