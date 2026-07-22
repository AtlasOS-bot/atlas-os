"""
Atlas v21 - Module 4: public finalization API.

finalize_collector_opportunity() takes one or more RawSourceInput
sources already known to describe the same opportunity (or lets this
module group them itself) and produces one FinalizedCollectorOpportunity:
a merged CollectorOpportunity, its Module 3 OpportunityEvaluation,
full evidence/conflict history, and (if an existing opportunity was
supplied) a field-level change summary.

finalize_collector_opportunities() is the batch entry point: it groups
an arbitrary set of sources into however many distinct opportunities
they actually describe, and finalizes each one independently.

Neither function ever mutates its inputs, writes to a database, or
duplicates Module 1/2/3 logic - merging happens in aggregator.py,
scoring happens by calling Module 3's evaluate_opportunity() as-is.
"""

from datetime import datetime, timezone

from collector_intelligence.aggregation_config import FinalizationConfig
from collector_intelligence.aggregation_models import (
    FinalizationBatchResult,
    FinalizedCollectorOpportunity,
    ManualReviewGroup,
    OpportunityChange,
    SourceDisposition,
)
from collector_intelligence.aggregator import build_candidates, merge_group
from collector_intelligence.decision_engine import evaluate_opportunity
from collector_intelligence.identity_matching import (
    identity_signature,
    identity_similarity,
    group_drafts,
)
from collector_intelligence.scoring import is_complete_set_mismatch


NOISY_CHANGE_FIELDS = {
    "created_at", "updated_at", "discovered_at", "last_verified_at",
    "opportunity_id", "raw_metadata", "score_explanation", "evidence",
    "normalized_product_name", "source_confidence", "reasoning",
}

MATERIAL_STATUS_TRANSITIONS = {"live", "sold_out", "restocked"}

ACQUISITION_CHANGE_FIELDS = {
    "membership_required", "lottery_required", "event_attendance_required",
    "bundle_required", "purchase_limit", "membership_exclusive",
}

PRICE_CHANGE_FIELDS = {
    "recent_sold_price", "current_market_price", "estimated_market_price",
    "retail_price", "required_spend",
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _to_disposition(candidate):
    source = candidate.source
    return SourceDisposition(
        source_title=source.title,
        source_name=source.source_name,
        source_type=source.source_type,
        source_url=source.source_url,
        disposition=candidate.disposition,
        reason=candidate.reason,
    )


def _is_material_change(field_name, previous_value, new_value, config):
    if field_name == "status":
        return new_value in MATERIAL_STATUS_TRANSITIONS or previous_value == "rumored"

    if field_name in ACQUISITION_CHANGE_FIELDS:
        return True

    if field_name in PRICE_CHANGE_FIELDS:
        if isinstance(previous_value, (int, float)) and isinstance(new_value, (int, float)) and previous_value:
            percent = abs(new_value - previous_value) / abs(previous_value) * 100
            return percent >= config.material_price_change_percent
        return previous_value != new_value

    if field_name in {"recommendation", "primary_strategy"}:
        return True

    if field_name == "opportunity_score":
        if isinstance(previous_value, (int, float)) and isinstance(new_value, (int, float)):
            return abs(new_value - previous_value) >= config.score_change_significance
        return False

    return False


def _build_change_summary(
    previous_opportunity, merged_opportunity, previous_evaluation, evaluation,
    config,
):
    changes = []

    if previous_opportunity is None:
        return changes

    previous_dict = previous_opportunity.to_dict()
    merged_dict = merged_opportunity.to_dict()

    for field_name, new_value in merged_dict.items():
        if field_name in NOISY_CHANGE_FIELDS:
            continue

        previous_value = previous_dict.get(field_name)

        if previous_value == new_value:
            continue

        if isinstance(new_value, (list, dict)) and not new_value and not previous_value:
            continue

        material = _is_material_change(field_name, previous_value, new_value, config)

        changes.append(OpportunityChange(
            field_name=field_name,
            previous_value=previous_value,
            new_value=new_value,
            reason=f"Updated by finalization merge for {field_name}",
            supporting_source=None,
            confidence_change=None,
            material_change=material,
        ))

    was_mismatch = is_complete_set_mismatch(previous_opportunity)
    now_mismatch = is_complete_set_mismatch(merged_opportunity)

    if was_mismatch and not now_mismatch:
        changes.append(OpportunityChange(
            field_name="complete_set_mismatch",
            previous_value=True,
            new_value=False,
            reason="New evidence confirmed the resale price refers to this "
                   "product itself, resolving the earlier unit-scope mismatch.",
            supporting_source=None,
            confidence_change=None,
            material_change=True,
        ))

    for field_name in ("recommendation", "primary_strategy", "opportunity_score"):
        previous_value = getattr(previous_evaluation, field_name)
        new_value = getattr(evaluation, field_name)

        if previous_value == new_value:
            continue

        changes.append(OpportunityChange(
            field_name=field_name,
            previous_value=previous_value,
            new_value=new_value,
            reason="Recalculated from the merged evidence via Module 3.",
            supporting_source=None,
            confidence_change=(
                round(evaluation.confidence_score - previous_evaluation.confidence_score, 2)
                if field_name == "recommendation" else None
            ),
            material_change=_is_material_change(field_name, previous_value, new_value, config),
        ))

    return changes


def _compute_confidences(merged_opportunity, conflicts, evidence, requires_manual_review):
    identity_fields = [
        "product_name", "brand", "franchise", "collaboration_partner",
    ]
    populated = sum(
        1 for f in identity_fields if getattr(merged_opportunity, f, None)
    )
    identity_confidence = (populated / len(identity_fields)) * 100

    identity_conflicts = [
        c for c in conflicts
        if c.field_name in identity_fields and c.requires_manual_review
    ]
    identity_confidence -= 25 * len(identity_conflicts)
    identity_confidence = max(0.0, min(100.0, identity_confidence))

    market_fields = ["recent_sold_price", "current_market_price", "estimated_market_price"]
    has_market_data = any(getattr(merged_opportunity, f, None) is not None for f in market_fields)

    market_confidence = 0.0
    if has_market_data:
        market_confidence = 70.0
        market_conflicts = [c for c in conflicts if c.field_name in market_fields]
        for c in market_conflicts:
            if c.requires_manual_review:
                market_confidence -= 30
            else:
                market_confidence -= 10
        market_confidence = max(0.0, min(100.0, market_confidence))

    finalization_confidence = (identity_confidence + (market_confidence or identity_confidence)) / 2
    if requires_manual_review:
        finalization_confidence *= 0.85
    finalization_confidence = round(max(0.0, min(100.0, finalization_confidence)), 2)

    return round(identity_confidence, 2), round(market_confidence, 2), finalization_confidence


def _finalize_group(group_candidates, existing_opportunity, context, config, finalization_config):
    merged_opportunity, evidence, conflicts, decisions, manual_review_reasons, warnings = merge_group(
        group_candidates, existing_opportunity, finalization_config,
    )

    previous_evaluation = (
        evaluate_opportunity(existing_opportunity, context=context, config=config)
        if existing_opportunity is not None else None
    )
    evaluation = evaluate_opportunity(merged_opportunity, context=context, config=config)

    requires_manual_review = bool(manual_review_reasons) or any(
        c.requires_manual_review for c in conflicts
    )

    if len(group_candidates) < 1:
        requires_manual_review = True
        manual_review_reasons.append("No accepted sources contributed to this group.")

    change_summary = _build_change_summary(
        existing_opportunity, merged_opportunity, previous_evaluation, evaluation,
        finalization_config,
    )

    previous_dedup_key = (
        existing_opportunity.dedup_key if existing_opportunity is not None else None
    )
    current_dedup_key = merged_opportunity.dedup_key

    if previous_dedup_key and previous_dedup_key != current_dedup_key:
        requires_manual_review = True
        manual_review_reasons.append(
            "Dedup key changed after merge - review before treating this as "
            "the same stored opportunity."
        )

    missing_information = list(evaluation.missing_information)

    identity_confidence, market_confidence, finalization_confidence = _compute_confidences(
        merged_opportunity, conflicts, evidence, requires_manual_review,
    )

    accepted_dispositions = [_to_disposition(c) for c in group_candidates]

    return FinalizedCollectorOpportunity(
        opportunity=merged_opportunity,
        evaluation=evaluation,
        source_results=accepted_dispositions,
        accepted_sources=accepted_dispositions,
        rejected_sources=[],
        merged_source_count=len(group_candidates),
        evidence_ledger=evidence,
        merge_decisions=decisions,
        conflicts=conflicts,
        warnings=warnings,
        missing_information=missing_information,
        identity_confidence=identity_confidence,
        market_confidence=market_confidence,
        finalization_confidence=finalization_confidence,
        change_summary=change_summary,
        previous_dedup_key=previous_dedup_key,
        current_dedup_key=current_dedup_key,
        requires_manual_review=requires_manual_review,
        manual_review_reasons=manual_review_reasons,
        finalized_at=_utc_now(),
    )


def finalize_collector_opportunity(
    sources,
    existing_opportunity=None,
    context=None,
    config=None,
    finalization_config=None,
):
    """
    Finalizes ONE opportunity from `sources` (all assumed to describe
    the same product - use finalize_collector_opportunities() for a
    mixed batch). `context`/`config` are Module 3's ScoringContext/
    ScoringConfig, passed straight through to evaluate_opportunity().
    `finalization_config` is this module's own FinalizationConfig
    (merge weights/thresholds) - kept as a separate parameter since it
    controls a different concern than Module 3's scoring config.
    """
    if isinstance(sources, (list, tuple)):
        source_list = list(sources)
    else:
        source_list = [sources]

    finalization_config = finalization_config or FinalizationConfig()

    candidates = build_candidates(source_list)
    accepted = [c for c in candidates if c.disposition.startswith("ACCEPTED")]

    if not accepted and existing_opportunity is None:
        reasons = "; ".join(f"{c.source.title!r}: {c.reason}" for c in candidates)
        raise ValueError(
            "No accepted sources - there is nothing to finalize an "
            f"opportunity from. Source dispositions: {reasons}"
        )

    accepted_ids = {id(c) for c in accepted}

    result = _finalize_group(
        accepted, existing_opportunity, context, config, finalization_config,
    )

    result.source_results = [_to_disposition(c) for c in candidates]
    result.rejected_sources = [
        _to_disposition(c) for c in candidates if id(c) not in accepted_ids
    ]

    return result


def finalize_collector_opportunities(
    sources,
    existing_opportunities=None,
    context=None,
    config=None,
    finalization_config=None,
):
    """
    Groups an arbitrary batch of sources into however many distinct
    opportunities they actually describe, and finalizes each group.
    `existing_opportunities` (optional) is matched to a group by
    identity similarity, not by input order.
    """
    finalization_config = finalization_config or FinalizationConfig()
    existing_opportunities = existing_opportunities or []

    candidates = build_candidates(list(sources))
    accepted = [c for c in candidates if c.disposition.startswith("ACCEPTED")]
    accepted_ids = {id(c) for c in accepted}
    rejected_candidates = [c for c in candidates if id(c) not in accepted_ids]

    warnings = []
    manual_review_groups = []
    finalized = []
    ungrouped = []

    if accepted:
        drafts = [c.draft for c in accepted]
        groups = group_drafts(drafts, finalization_config.identity_match_threshold)

        for index_group in groups:
            group_candidates = [accepted[i] for i in index_group]

            if len(index_group) == 1 and len(groups) > 2:
                # Only genuinely ambiguous when this source has partial
                # (sub-threshold) similarity with TWO OR MORE distinct
                # other groups - "torn between multiple candidates," not
                # merely "not similar enough to the one other product in
                # a two-group batch" (that's just two different products,
                # which is expected and should finalize separately).
                lone_signature = identity_signature(group_candidates[0].draft)
                partial_matches = 0

                for other_index_group in groups:
                    if other_index_group is index_group:
                        continue
                    other_draft = accepted[other_index_group[0]].draft
                    other_signature = identity_signature(other_draft)
                    similarity = identity_similarity(lone_signature, other_signature)

                    if 0 < similarity < finalization_config.identity_match_threshold:
                        partial_matches += 1

                if partial_matches >= 2:
                    manual_review_groups.append(ManualReviewGroup(
                        source_titles=[group_candidates[0].source.title],
                        reason=(
                            "This source has partial identity overlap with more "
                            "than one other group - too ambiguous to merge "
                            "automatically."
                        ),
                    ))
                    ungrouped.append(_to_disposition(group_candidates[0]))
                    continue

            existing_match = None
            for existing in existing_opportunities:
                if identity_similarity(
                    identity_signature(group_candidates[0].draft),
                    identity_signature(existing),
                ) >= finalization_config.identity_match_threshold:
                    existing_match = existing
                    break

            finalized_group = _finalize_group(
                group_candidates, existing_match, context, config, finalization_config,
            )
            finalized_group.source_results = [_to_disposition(c) for c in group_candidates]
            finalized.append(finalized_group)

    result = FinalizationBatchResult(
        finalized_opportunities=finalized,
        ungrouped_sources=ungrouped,
        rejected_sources=[_to_disposition(c) for c in rejected_candidates],
        manual_review_groups=manual_review_groups,
        total_sources=len(candidates),
        accepted_source_count=len(accepted),
        rejected_source_count=len(rejected_candidates),
        group_count=len(finalized),
        warnings=warnings,
    )

    return result
