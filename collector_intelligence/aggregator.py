"""
Atlas v21 - Module 4: source classification and group merging.

Two responsibilities live here:

1. build_candidates(): run every source through Module 2, classify its
   disposition (accepted/rejected, and which kind), and build its
   per-field evidence records. Never raises for a bad/irrelevant
   source - it becomes a rejected candidate instead.

2. merge_group(): given a set of accepted candidates already confirmed
   (by identity_matching) to describe the same opportunity, resolve
   every field to one value, track every conflict, and produce a
   merged CollectorOpportunity - optionally folded into an
   existing_opportunity without mutating it.
"""

from dataclasses import dataclass

from collector_intelligence.aggregation_config import FinalizationConfig
from collector_intelligence.aggregation_models import FieldConflict, MergeDecision
from collector_intelligence.conflict_resolution import (
    IDENTITY_CRITICAL_FIELDS,
    _is_more_specific,
    priority_rank,
    resolve_field,
)
from collector_intelligence.detector import detect_signals
from collector_intelligence.evidence_ledger import build_evidence_records
from collector_intelligence.models import CollectorOpportunity
from collector_intelligence.normalize import normalize_text
from collector_intelligence.opportunity_builder import (
    InsufficientIdentityError,
    build_partial_opportunity,
)
from collector_intelligence.signals import SignalType


STATUS_TIER_A = {"OFFICIAL", "RETAILER", "PRESS_RELEASE", "EVENT"}
PRIMARY_SOURCE_TYPES = {"OFFICIAL", "RETAILER", "PRESS_RELEASE", "EVENT"}
WEAK_SOURCE_TYPES = {"COMMUNITY", "SOCIAL", "OTHER"}
STATUS_SIGNAL_TYPES = {
    SignalType.STATUS_SOLD_OUT.value,
    SignalType.STATUS_RESTOCKED.value,
    SignalType.STATUS_LIVE.value,
    SignalType.LOW_STOCK.value,
}

MARKET_PRICE_FIELDS = (
    "recent_sold_price", "current_market_price", "estimated_market_price",
)

# Fields a human may have manually corrected on an existing opportunity
# - never silently overwritten by a fresh merge unless config allows it
# or the new evidence is a strictly more specific identity value.
PROTECTED_UNLESS_OVERWRITE_ALLOWED = {
    "retail_price", "required_spend", "purchase_limit", "stated_quantity",
    "numbered", "first_edition", "first_collaboration", "anniversary_release",
    "exclusive_promo", "exclusive_artwork", "exclusive_character",
    "event_exclusive", "convention_exclusive", "tournament_exclusive",
    "membership_exclusive", "membership_required", "lottery_required",
    "event_attendance_required", "bundle_required", "sealed_product",
    "redeemable_reward", "release_date", "announcement_date", "release_time",
    "purchase_window_start", "purchase_window_end",
}

@dataclass
class SourceCandidate:
    source: object
    result: object | None
    draft: CollectorOpportunity | None
    disposition: str
    reason: str
    evidence: list


# ---------------------------------------------------------------
# Source classification
# ---------------------------------------------------------------

def _dedup_probe(source):
    if source.source_url:
        return f"url:{source.source_url.strip().lower()}"

    text = normalize_text(source.full_text)
    return f"text:{text}" if text else None


def _classify_accepted_kind(source, result):
    has_rumor = any(
        detection.rumored or detection.signal_type == SignalType.RUMOR.value
        for detection in result.detected_signals
    )

    if has_rumor:
        return "ACCEPTED_RUMOR", "Source contains rumor/unconfirmed language."

    if source.source_type == "MARKETPLACE":
        return (
            "ACCEPTED_MARKET_EVIDENCE",
            "Marketplace source - used for resale price evidence only, "
            "not product identity.",
        )

    if source.source_type in PRIMARY_SOURCE_TYPES:
        return (
            "ACCEPTED_PRIMARY",
            f"{source.source_type} source - authoritative for identity "
            f"and acquisition rules.",
        )

    signal_types_present = {d.signal_type for d in result.detected_signals}

    if signal_types_present & STATUS_SIGNAL_TYPES:
        return (
            "ACCEPTED_STATUS_UPDATE",
            "Source primarily reports an availability/status change.",
        )

    return (
        "ACCEPTED_SUPPORTING",
        "Source provides supporting/corroborating evidence.",
    )


def build_candidates(sources, threshold=35):
    """
    Runs every source through Module 2 and classifies it. Never fails
    the batch for one bad source.
    """
    candidates = []
    seen = set()

    for source in sources:
        probe = _dedup_probe(source)

        if probe and probe in seen:
            candidates.append(SourceCandidate(
                source, None, None, "REJECTED_DUPLICATE",
                "Duplicate of an earlier source in this batch (same URL "
                "or identical content).",
                [],
            ))
            continue

        if probe:
            seen.add(probe)

        result = detect_signals(source, threshold=threshold)

        if not result.detected_signals and not result.extracted_entities.has_any_identity():
            candidates.append(SourceCandidate(
                source, result, None, "REJECTED_IRRELEVANT",
                "No collector-relevant signals or identifiable product "
                "detected in this source.",
                [],
            ))
            continue

        # Module 4 deliberately does NOT defer to should_create_opportunity
        # here - that flag answers "would THIS SOURCE ALONE justify a new
        # opportunity," which is a stricter bar than "is this source valid
        # supporting evidence once combined with others" (Module 4's whole
        # purpose). A source is only rejected outright when it truly can't
        # be tied to a product, or contributes zero corroborating signals.
        try:
            draft = build_partial_opportunity(result)
        except InsufficientIdentityError:
            candidates.append(SourceCandidate(
                source, result, None, "REJECTED_IRRELEVANT",
                "Could not resolve a product identity from this source.",
                [],
            ))
            continue

        if not result.detected_signals:
            candidates.append(SourceCandidate(
                source, result, None, "REJECTED_TOO_WEAK",
                "Source has no extractable signals beyond an unverified "
                "identity hint.",
                [],
            ))
            continue

        disposition, reason = _classify_accepted_kind(source, result)
        evidence = build_evidence_records(source, result, draft)
        candidates.append(SourceCandidate(
            source, result, draft, disposition, reason, evidence
        ))

    return candidates


# ---------------------------------------------------------------
# Status resolution (preserves full history)
# ---------------------------------------------------------------

def _resolve_status(records):
    if not records:
        return None, [], None

    history = [
        {
            "status": r.proposed_value,
            "source_name": r.source_name,
            "source_type": r.source_type,
            "observed_at": r.observed_at,
        }
        for r in records
    ]
    history.sort(key=lambda entry: entry["observed_at"] or "")

    tier_a = [r for r in records if r.source_type in STATUS_TIER_A]
    pool = tier_a if tier_a else records

    chosen = max(pool, key=lambda r: r.observed_at or "")

    for r in records:
        if r is chosen:
            r.accepted = True
        else:
            r.accepted = False
            r.rejection_reason = (
                "superseded by a more recent status observation"
                if r.source_type in STATUS_TIER_A or not tier_a
                else "lower-authority source than an available status update"
            )

    conflict = None
    distinct = {r.proposed_value for r in records}

    if len(distinct) > 1:
        conflict = FieldConflict(
            field_name="status",
            competing_values=sorted(distinct),
            evidence_references=[
                r.source_name or r.source_type or "unknown" for r in records
            ],
            severity="INFO",
            resolution=(
                f"Current status set to {chosen.proposed_value!r} from the "
                f"most recent {'authoritative' if tier_a else 'available'} "
                f"source."
            ),
            auto_resolved=True,
            requires_manual_review=False,
            explanation=(
                "Status evolved across sources; the full history is "
                "preserved separately from the current value."
            ),
        )

    return chosen.proposed_value, history, conflict


# ---------------------------------------------------------------
# Market price resolution (unit-scope aware, outlier-aware)
# ---------------------------------------------------------------

def _partition_outliers(records, ratio_threshold):
    numeric = [r for r in records if isinstance(r.proposed_value, (int, float))]

    if len(numeric) < 2:
        return numeric, []

    values = sorted(r.proposed_value for r in numeric)
    mid = len(values) // 2
    median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2

    inliers, outliers = [], []
    for r in numeric:
        ratio = (r.proposed_value / median) if median else 1.0
        if ratio > ratio_threshold or ratio < (1 / ratio_threshold):
            outliers.append(r)
        else:
            inliers.append(r)

    return inliers, outliers


def _resolve_market_prices(grouped, config):
    """
    Resolves recent_sold_price / current_market_price /
    estimated_market_price. Source AUTHORITY (via field_source_priority
    - MARKETPLACE ranks highest for these fields) decides which value
    wins when observations disagree, not a guessed "product scope"
    derived from the product's own name - a weak source's incorrect
    unit claim must never silently outrank a stronger source's correct
    one just because it happens to textually match the product title.
    Disagreeing unit scopes are always surfaced as a conflict.
    """
    conflicts = []
    decisions = []
    resolved = {}
    extra_risks = []
    manual_review_reasons = []
    warnings = []
    chosen_pools = {}

    for field_name in MARKET_PRICE_FIELDS:
        records = grouped.pop(field_name, [])

        if not records:
            continue

        if field_name == "estimated_market_price" and not config.allow_asking_price_as_market_estimate:
            for r in records:
                r.accepted = False
                r.rejection_reason = (
                    "asking prices are not permitted to populate market "
                    "estimates (configuration)"
                )
            continue

        inliers, outliers = _partition_outliers(records, config.price_outlier_ratio)
        candidate_pool = inliers if (inliers and outliers) else (inliers or records)

        if outliers and inliers:
            conflicts.append(FieldConflict(
                field_name=field_name,
                competing_values=[r.proposed_value for r in records if isinstance(r.proposed_value, (int, float))],
                evidence_references=[
                    r.source_name or r.source_type or "unknown" for r in outliers
                ],
                severity="MEDIUM",
                resolution=(
                    f"Rejected {len(outliers)} outlier observation(s); kept "
                    f"{len(inliers)} consistent observation(s)."
                ),
                auto_resolved=True,
                requires_manual_review=False,
                explanation=(
                    f"{len(outliers)} of {len(inliers) + len(outliers)} "
                    f"observations deviated more than {config.price_outlier_ratio}x "
                    f"from the median and were excluded as outliers."
                ),
            ))

        if len(candidate_pool) >= 2:
            vals = sorted(r.proposed_value for r in candidate_pool)
            mid = len(vals) // 2
            representative_value = (
                vals[mid] if len(vals) % 2
                else round((vals[mid - 1] + vals[mid]) / 2, 2)
            )
            rule = f"median of {len(candidate_pool)} consistent observations"
        else:
            representative_value = candidate_pool[0].proposed_value
            rule = "single observation"

        authority_record = max(
            candidate_pool,
            key=lambda r: (priority_rank(field_name, r.source_type, config), r.confidence),
        )

        chosen_ids = {id(r) for r in candidate_pool}
        outlier_ids = {id(r) for r in outliers}

        for r in records:
            if id(r) in chosen_ids:
                r.accepted = True
            elif id(r) in outlier_ids:
                r.accepted = False
                r.rejection_reason = (
                    "statistical outlier relative to other consistent "
                    "observations"
                )
            else:
                r.accepted = False
                r.rejection_reason = "not selected - superseded by other evidence"

        resolved[field_name] = representative_value
        chosen_pools[field_name] = candidate_pool

        decisions.append(MergeDecision(
            field_name=field_name,
            chosen_value=representative_value,
            chosen_source=", ".join(sorted({
                (r.source_name or r.source_type or "unknown") for r in candidate_pool
            })),
            rule_applied=rule,
            alternative_values=[
                r.proposed_value for r in records if id(r) not in chosen_ids
            ],
        ))

        distinct_scopes = {
            r.unit_scope for r in records if r.unit_scope and r.unit_scope != "unknown"
        }

        if len(distinct_scopes) > 1:
            manual_review_reasons.append(f"Unit-scope conflict for {field_name}")
            conflicts.append(FieldConflict(
                field_name=field_name,
                competing_values=sorted(distinct_scopes),
                evidence_references=[
                    r.source_name or r.source_type or "unknown"
                    for r in records if r.unit_scope and r.unit_scope != "unknown"
                ],
                severity="HIGH",
                resolution=(
                    f"Used the {authority_record.unit_scope or 'unscoped'} "
                    f"observation from "
                    f"{authority_record.source_name or authority_record.source_type} "
                    f"(the highest-authority source for {field_name})."
                ),
                auto_resolved=True,
                requires_manual_review=True,
                explanation=(
                    f"Sources disagree on what unit this {field_name} evidence "
                    f"describes ({', '.join(sorted(distinct_scopes))}). The "
                    f"most authoritative source's reading was used, but this "
                    f"must be verified before treating the figure as confirmed "
                    f"for a single unit."
                ),
            ))
        elif not distinct_scopes:
            manual_review_reasons.append(f"Unknown unit scope for {field_name}")
            warnings.append(
                f"Unit scope for {field_name} evidence could not be "
                f"determined."
            )
        elif next(iter(distinct_scopes)) not in ("single_item",):
            extra_risks.append(
                f"Resale evidence for {field_name} refers to a "
                f"{next(iter(distinct_scopes)).replace('_', ' ')}, not "
                f"necessarily a single item - treat with caution."
            )

        if len(candidate_pool) < config.minimum_market_observations:
            warnings.append(
                f"{field_name} is based on fewer than "
                f"{config.minimum_market_observations} observation(s) - "
                f"confidence is limited."
            )

        grading_records = grouped.pop(f"{field_name}__grading", [])
        distinct_grading = {r.proposed_value for r in grading_records}

        if len(distinct_grading) > 1:
            manual_review_reasons.append(f"Graded/ungraded conflict for {field_name}")
            conflicts.append(FieldConflict(
                field_name=field_name,
                competing_values=sorted(distinct_grading),
                evidence_references=[
                    r.source_name or r.source_type or "unknown" for r in grading_records
                ],
                severity="HIGH",
                resolution=(
                    f"{field_name} evidence mixes graded and ungraded condition "
                    f"reports - condition was not normalized automatically."
                ),
                auto_resolved=False,
                requires_manual_review=True,
                explanation=(
                    "Graded and ungraded items can carry very different resale "
                    "values; mixing them without normalization would misstate "
                    "the price."
                ),
            ))

    return resolved, conflicts, decisions, extra_risks, manual_review_reasons, warnings, chosen_pools


def _check_extreme_resale(resolved_values, chosen_pools, config):
    spend = resolved_values.get("required_spend") or resolved_values.get("retail_price")

    if not spend:
        return None

    for field_name in MARKET_PRICE_FIELDS:
        pool = chosen_pools.get(field_name)
        value = resolved_values.get(field_name)

        if not pool or not value:
            continue

        ratio = value / spend if spend else 0

        if ratio >= config.extreme_resale_multiplier and all(
            r.source_type in WEAK_SOURCE_TYPES for r in pool
        ):
            return field_name, ratio

    return None


# ---------------------------------------------------------------
# Group merge
# ---------------------------------------------------------------

def merge_group(candidates, existing_opportunity=None, config=None):
    """
    Merges one identity-matched group of accepted SourceCandidates
    (optionally folded into an existing CollectorOpportunity, which is
    never mutated) into a single CollectorOpportunity plus the
    supporting evidence ledger, conflicts, and merge decisions.
    """
    config = config or FinalizationConfig()

    all_evidence = []
    for candidate in candidates:
        all_evidence.extend(candidate.evidence)

    grouped = {}
    for record in all_evidence:
        if record.field_name.endswith("__price_kind"):
            continue
        if record.field_name == "pack_quantity_note":
            continue
        grouped.setdefault(record.field_name, []).append(record)

    resolved_values = {}
    conflicts = []
    decisions = []
    manual_review_reasons = []
    warnings = []

    # --- Identity fields resolved first, for readability/traceability. ---
    for field_name in ("product_name", "edition_name", "category"):
        records = grouped.pop(field_name, [])
        if not records:
            continue
        value, conflict, decision = resolve_field(field_name, records, config)
        if value is not None:
            resolved_values[field_name] = value
        if conflict:
            conflicts.append(conflict)
        if decision:
            decisions.append(decision)

    # --- Status (history-aware) ---
    status_records = grouped.pop("status", [])
    status_value, status_history, status_conflict = _resolve_status(status_records)
    if status_value:
        resolved_values["status"] = status_value
    if status_conflict:
        conflicts.append(status_conflict)

    # --- Market prices (authority + outlier aware) ---
    (
        market_values, market_conflicts, market_decisions, extra_risks,
        market_review_reasons, market_warnings, chosen_pools,
    ) = _resolve_market_prices(grouped, config)
    resolved_values.update(market_values)
    conflicts.extend(market_conflicts)
    decisions.extend(market_decisions)
    manual_review_reasons.extend(market_review_reasons)
    warnings.extend(market_warnings)

    # --- Everything else, generically ---
    for field_name, records in list(grouped.items()):
        value, conflict, decision = resolve_field(field_name, records, config)
        if value is not None:
            resolved_values[field_name] = value
        if conflict:
            conflicts.append(conflict)
            if conflict.requires_manual_review:
                manual_review_reasons.append(
                    f"{field_name}: {conflict.explanation}"
                )
        if decision:
            decisions.append(decision)

    # --- Extreme resale claim from weak sources only ---
    extreme = _check_extreme_resale(resolved_values, chosen_pools, config)
    if extreme:
        field_name, ratio = extreme
        extra_risks.append(
            f"Reported {field_name.replace('_', ' ')} is {ratio:.1f}x the "
            f"acquisition cost and is supported only by community/social "
            f"sources - treat as an unverified claim."
        )
        manual_review_reasons.append(
            f"Extreme resale claim ({ratio:.1f}x spend) from weak sources only"
        )

    # --- Additive fields (union across all sources, not "pick one").
    # Seeded from the existing opportunity so a later finalization
    # round doesn't discard history accumulated by earlier rounds.
    catalyst_signals = (
        list(existing_opportunity.catalyst_signals)
        if existing_opportunity is not None else []
    )
    risks = (
        list(existing_opportunity.risks) if existing_opportunity is not None else []
    )
    for item in extra_risks:
        if item not in risks:
            risks.append(item)
    for candidate in candidates:
        for item in candidate.draft.catalyst_signals:
            if item not in catalyst_signals:
                catalyst_signals.append(item)
        for item in candidate.draft.risks:
            if item not in risks:
                risks.append(item)
    if catalyst_signals:
        resolved_values["catalyst_signals"] = catalyst_signals
    if risks:
        resolved_values["risks"] = risks

    # Evidence and status history accumulate across finalization rounds
    # - a later round must never erase what an earlier round recorded.
    previous_evidence = (
        list(existing_opportunity.evidence) if existing_opportunity is not None else []
    )
    resolved_values["evidence"] = previous_evidence + [
        record.to_dict() for record in all_evidence
    ]

    previous_status_history = (
        list(existing_opportunity.raw_metadata.get("status_history", []))
        if existing_opportunity is not None else []
    )
    combined_status_history = previous_status_history + status_history
    if combined_status_history:
        resolved_values["raw_metadata"] = {"status_history": combined_status_history}

    # The opportunity's own source_* fields describe its single most
    # authoritative contributing source, not any one field's evidence.
    # This must also weigh the EXISTING opportunity's own provenance -
    # a prior official source's authority isn't forgotten just because
    # this round's new sources happen to be lower-tier.
    best_new_candidate = max(
        candidates,
        key=lambda c: config.source_type_weights.get(c.source.source_type, 0),
    )
    best_new_weight = config.source_type_weights.get(
        best_new_candidate.source.source_type, 0
    )
    existing_weight = (
        config.source_type_weights.get(existing_opportunity.source_type, -1)
        if existing_opportunity is not None else -1
    )

    if existing_weight > best_new_weight:
        resolved_values["source_name"] = existing_opportunity.source_name
        resolved_values["source_type"] = existing_opportunity.source_type
        resolved_values["source_url"] = existing_opportunity.source_url
        resolved_values["source_published_at"] = existing_opportunity.source_published_at
    else:
        resolved_values["source_name"] = best_new_candidate.source.source_name
        resolved_values["source_type"] = best_new_candidate.source.source_type
        resolved_values["source_url"] = best_new_candidate.source.source_url
        resolved_values["source_published_at"] = best_new_candidate.source.published_at

    # --- Fold into existing_opportunity without mutating it ---
    merged_opportunity, protected_overwrites = _build_final_opportunity(
        resolved_values, existing_opportunity, config
    )

    for field_name, existing_value, proposed_value in protected_overwrites:
        manual_review_reasons.append(
            f"Existing value for {field_name} ({existing_value!r}) was "
            f"preserved; new evidence proposed {proposed_value!r} but "
            f"overwriting manual values is disabled."
        )
        warnings.append(
            f"New evidence for {field_name} was not applied - an existing "
            f"value is protected from automatic overwrite."
        )

    return (
        merged_opportunity, all_evidence, conflicts, decisions,
        manual_review_reasons, warnings,
    )


def _build_final_opportunity(resolved_values, existing_opportunity, config):
    base = {}

    if existing_opportunity is not None:
        base = existing_opportunity.to_dict()
        for key in ("normalized_product_name", "dedup_key", "created_at", "updated_at"):
            base.pop(key, None)

    final = dict(base)
    protected_overwrites = []

    for field_name, value in resolved_values.items():
        existing_value = base.get(field_name)
        is_protected_field = field_name in PROTECTED_UNLESS_OVERWRITE_ALLOWED

        has_existing_value = existing_value not in (None, [], {}, "")

        if (
            existing_opportunity is not None
            and has_existing_value
            and is_protected_field
            and not config.allow_manual_value_overwrite
        ):
            protected_overwrites.append((field_name, existing_value, value))
            continue

        if (
            existing_opportunity is not None
            and has_existing_value
            and field_name in IDENTITY_CRITICAL_FIELDS
            and not config.allow_manual_value_overwrite
        ):
            if _is_more_specific(value, existing_value):
                final[field_name] = value
            else:
                protected_overwrites.append((field_name, existing_value, value))
            continue

        final[field_name] = value

    if existing_opportunity is not None:
        final["opportunity_id"] = existing_opportunity.opportunity_id

    final.pop("dedup_key", None)

    merged = CollectorOpportunity.from_dict(final)
    return merged, protected_overwrites
