"""
Atlas v21 - Module 7: catalog-side source health state.

Consumes Module 6 ConnectorHealth (and optional change-detection
timestamps) to compute a SourceHealthState and a recommended catalog
action. Never mutates the catalog - recommendations only.
"""

from datetime import datetime, timezone

from collector_intelligence.catalog_models import SourceHealthState


def _utc_now():
    return datetime.now(timezone.utc)


def _parse(ts):
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def evaluate_source_health(source, connector_health=None, last_change_detected_at=None, now=None):
    """
    `connector_health` is a Module 6 ConnectorHealth (or None if the
    source has never been run). Returns a SourceHealthState plus a
    recommended_catalog_action - the catalog itself is never touched.
    """
    now = now or _utc_now()
    policy = source.health_policy

    if not source.enabled or source.lifecycle_state in ("retired", "broken"):
        return SourceHealthState(
            source_id=source.source_id,
            health_status="disabled",
            recommended_catalog_action="none",
        )

    if connector_health is None:
        return SourceHealthState(
            source_id=source.source_id,
            health_status="unknown",
            recommended_catalog_action="none",
        )

    last_success = _parse(connector_health.last_success_at)
    consecutive_failures = connector_health.consecutive_failures

    stale_since = None
    if last_success:
        age_hours = (now - last_success).total_seconds() / 3600.0
        if age_hours > policy.stale_after:
            stale_since = connector_health.last_success_at

    if consecutive_failures >= policy.disable_after_failures:
        status = "failing"
        action = "pause" if policy.permanent_failure_action == "pause" else policy.permanent_failure_action
    elif consecutive_failures >= policy.max_consecutive_failures:
        status = "failing"
        action = "inspect"
    elif stale_since:
        status = "stale"
        action = "inspect"
    elif consecutive_failures > 0:
        status = "warning"
        action = "retry"
    else:
        status = "healthy"
        action = "none"

    if last_success is None and consecutive_failures == 0:
        status = "unknown"
        action = "none"

    return SourceHealthState(
        source_id=source.source_id,
        last_success_at=connector_health.last_success_at,
        last_failure_at=None if connector_health.healthy else connector_health.checked_at,
        consecutive_failures=consecutive_failures,
        last_error_code=(
            connector_health.last_error.split(":")[0] if connector_health.last_error else None
        ),
        last_change_detected_at=last_change_detected_at,
        stale_since=stale_since,
        health_status=status,
        recommended_catalog_action=action,
    )
