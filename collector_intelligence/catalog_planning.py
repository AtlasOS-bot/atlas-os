"""
Atlas v21 - Module 7: connector execution planning.

build_connector_plan() turns a validated catalog into a deterministic,
deduplicated list of what to fetch and in what order - it never
fetches anything itself (that's Module 6's job, invoked separately by
the caller with the plan this module produces).
"""

from datetime import datetime, timezone

from collector_intelligence.catalog_models import (
    AUTHORITY_RANK,
    PRIORITY_RANK,
    ConnectorExecutionItem,
    ConnectorExecutionPlan,
    ScheduleSpec,
)
from collector_intelligence.catalog_validation import validate_catalog
from collector_intelligence.connector_models import ScheduleState
from collector_intelligence.connector_scheduler import compute_next_run


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def resolve_schedule(source, owning_scouts, catalog):
    """
    source schedule > scout default schedule > catalog default > manual.
    When a source has multiple owning scouts, the first (by scout_id,
    for determinism) scout with a non-empty default_schedule wins.
    """
    if not source.schedule.is_empty():
        return source.schedule

    for scout in sorted(owning_scouts, key=lambda s: s.scout_id):
        if not scout.default_schedule.is_empty():
            return scout.default_schedule

    catalog_default = (catalog.metadata or {}).get("default_schedule")
    if catalog_default:
        return ScheduleSpec(
            mode=catalog_default.get("mode"),
            cron_expression=catalog_default.get("cron_expression"),
        )

    return ScheduleSpec(mode="manual")


def resolve_connector_config(source, owning_scouts, catalog):
    """
    Deterministic, non-mutating merge: catalog default < scout default
    (merged in scout_id order, later scouts win ties) < source config.
    Returns a brand-new dict every time.
    """
    merged = dict((catalog.metadata or {}).get("default_connector_config") or {})

    for scout in sorted(owning_scouts, key=lambda s: s.scout_id):
        merged.update(scout.default_connector_config)

    merged.update(source.connector_config)
    return merged


def resolve_source_priority(catalog, source):
    """A source's own priority is inherited from the BEST (numerically
    lowest-rank) priority among its owning scouts, since a source with
    no scouts (orphaned/manual) defaults to 'medium'."""
    owning_scouts = [catalog.scouts[sid] for sid in source.scout_ids if sid in catalog.scouts]
    if not owning_scouts:
        return "medium"
    return min((s.priority for s in owning_scouts), key=lambda p: PRIORITY_RANK.get(p, 99))


def is_source_due(catalog, source, now=None):
    """
    Returns (due: bool, reason: str). The static catalog carries no
    last-run timestamp (that's Module 6's runtime concern, tracked per
    connector run, not per catalog entry) - so "due" here means "this
    source has an active automatic schedule and would participate in
    a scheduled run," not "a full period has elapsed since it last
    ran." Callers who need true recency-aware due-checking should
    cross-reference Module 6 ConnectorHealth/ScheduleState themselves.
    """
    now = now or datetime.now(timezone.utc)
    owning_scouts = [catalog.scouts[sid] for sid in source.scout_ids if sid in catalog.scouts]
    schedule_spec = resolve_schedule(source, owning_scouts, catalog)

    if schedule_spec.mode in (None, "manual"):
        return False, "schedule is manual - never automatically due"

    if schedule_spec.mode == "disabled":
        return False, "schedule is disabled"

    state = ScheduleState(mode=schedule_spec.mode, cron_expression=schedule_spec.cron_expression)

    try:
        next_run = compute_next_run(state, now=now)
    except ValueError as exc:
        return False, f"invalid schedule: {exc}"

    if next_run is None:
        return False, "schedule has no computable next run"

    return True, f"schedule mode is {schedule_spec.mode!r} - eligible for automatic execution"


def build_connector_plan(catalog, scout_names=None, source_ids=None, now=None, config=None):
    now = now or datetime.now(timezone.utc)

    validation = validate_catalog(catalog, config)
    warnings = [f"{w.path}: {w.message}" for w in validation.warnings]

    if not validation.valid:
        return ConnectorExecutionPlan(
            generated_at=_utc_now(),
            warnings=warnings + [f"{e.path}: {e.message}" for e in validation.errors],
            invalid_items=[{"path": e.path, "message": e.message} for e in validation.errors],
        )

    catalog = validation.normalized_catalog

    if scout_names:
        selected_scout_ids = {s if s in catalog.scouts else s for s in scout_names}
        candidate_source_ids = set()
        for scout_id in selected_scout_ids:
            scout = catalog.scouts.get(scout_id)
            if scout:
                candidate_source_ids.update(scout.source_ids)
    elif source_ids:
        candidate_source_ids = set(source_ids)
    else:
        candidate_source_ids = set(catalog.sources)

    items = []
    disabled_items = []
    invalid_items = []
    allow_proposed = bool(config and config.allow_proposed_sources_in_plan)

    for source_id in sorted(candidate_source_ids):
        source = catalog.sources.get(source_id)
        if source is None:
            invalid_items.append({"source_id": source_id, "reason": "source_id not found in catalog"})
            continue

        if not source.enabled:
            disabled_items.append({"source_id": source_id, "reason": "source is disabled"})
            continue

        if source.lifecycle_state == "retired":
            disabled_items.append({"source_id": source_id, "reason": "source is retired"})
            continue

        if source.lifecycle_state == "broken":
            invalid_items.append({"source_id": source_id, "reason": "source is marked broken"})
            continue

        if source.lifecycle_state == "paused":
            disabled_items.append({"source_id": source_id, "reason": "source is paused"})
            continue

        if source.lifecycle_state == "proposed" and not allow_proposed:
            disabled_items.append({
                "source_id": source_id,
                "reason": "source is proposed - excluded unless allow_proposed_sources_in_plan is set",
            })
            continue

        if source.connector_type is None:
            invalid_items.append({"source_id": source_id, "reason": "source has no connector_type (manual-only source)"})
            continue

        item_warning = None
        if source.lifecycle_state == "deprecated":
            deprecated_policy = (config.deprecated_source_policy if config else "run_with_warning")
            if deprecated_policy == "exclude":
                disabled_items.append({"source_id": source_id, "reason": "source is deprecated (policy: exclude)"})
                continue
            item_warning = f"source {source_id!r} is deprecated"
            warnings.append(item_warning)

        owning_scouts = [catalog.scouts[sid] for sid in source.scout_ids if sid in catalog.scouts]
        owning_scout_ids = sorted(s.scout_id for s in owning_scouts)

        if not owning_scout_ids:
            warnings.append(f"source {source_id!r} has no owning scout - executing unscoped")

        due, due_reason = is_source_due(catalog, source, now=now)
        schedule_spec = resolve_schedule(source, owning_scouts, catalog)
        connector_config = resolve_connector_config(source, owning_scouts, catalog)
        priority = resolve_source_priority(catalog, source)

        primary_scout_id = owning_scout_ids[0] if owning_scout_ids else ""

        items.append(ConnectorExecutionItem(
            scout_id=primary_scout_id,
            source_id=source.source_id,
            connector_name=source.connector_type,
            source_url=source.url,
            schedule=schedule_spec.to_dict(),
            connector_config=connector_config,
            authority_level=source.authority_level,
            expected_evidence=source.expected_evidence.to_dict(),
            priority=priority,
            due=due,
            due_reason=due_reason,
            metadata={"owning_scout_ids": owning_scout_ids},
        ))

    items.sort(key=lambda item: (
        0 if item.due else 1,
        PRIORITY_RANK.get(item.priority, 99),
        AUTHORITY_RANK.get(item.authority_level, 99),
        item.scout_id,
        item.source_id,
    ))

    due_items = [i for i in items if i.due]
    skipped_items = [i for i in items if not i.due]

    return ConnectorExecutionPlan(
        generated_at=_utc_now(),
        items=items,
        due_items=due_items,
        skipped_items=skipped_items,
        disabled_items=disabled_items,
        invalid_items=invalid_items,
        warnings=warnings,
    )
