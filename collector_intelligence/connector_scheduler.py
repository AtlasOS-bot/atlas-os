"""
Atlas v21 - Module 6: scheduler infrastructure.

This computes WHEN a connector should next run and tracks failure
backoff - it never runs anything itself or loops continuously.
Callers (a future cron job, worker process, etc.) are responsible for
actually invoking the connector at the computed time.
"""

from datetime import datetime, timedelta, timezone

VALID_MODES = frozenset({"manual", "hourly", "daily", "cron", "disabled"})


def _parse_cron_field(field, min_value, max_value):
    if field == "*":
        return set(range(min_value, max_value + 1))

    values = set()
    for part in field.split(","):
        if part.startswith("*/"):
            step = int(part[2:])
            values.update(range(min_value, max_value + 1, step))
        elif "-" in part:
            low, high = part.split("-")
            values.update(range(int(low), int(high) + 1))
        else:
            values.add(int(part))

    return values


def compute_next_cron_run(expression, now, max_minutes_ahead=366 * 24 * 60):
    """
    Minimal but correct 5-field cron evaluator (minute hour day month
    weekday; weekday 0=Sunday). Brute-forces forward minute by minute
    - simple, deterministic, and more than fast enough since this is
    never called in a hot loop (it's scheduling infrastructure, not a
    scheduler that runs continuously).
    """
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError(f"Unsupported cron expression: {expression!r} (expected 5 fields)")

    minute_field, hour_field, day_field, month_field, weekday_field = parts
    minutes = _parse_cron_field(minute_field, 0, 59)
    hours = _parse_cron_field(hour_field, 0, 23)
    days = _parse_cron_field(day_field, 1, 31)
    months = _parse_cron_field(month_field, 1, 12)
    weekdays = _parse_cron_field(weekday_field, 0, 6)

    candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

    for _ in range(max_minutes_ahead):
        if (
            candidate.minute in minutes and candidate.hour in hours
            and candidate.day in days and candidate.month in months
            and (candidate.isoweekday() % 7) in weekdays
        ):
            return candidate.isoformat()
        candidate += timedelta(minutes=1)

    return None


def compute_next_run(schedule, now=None):
    """Returns an ISO timestamp string, or None if there is no next
    run to schedule (manual/disabled modes)."""
    now = now or datetime.now(timezone.utc)

    if schedule.mode not in VALID_MODES:
        raise ValueError(f"Unknown schedule mode: {schedule.mode!r}")

    if schedule.backoff_until:
        backoff_until = datetime.fromisoformat(schedule.backoff_until)
        if backoff_until > now:
            return schedule.backoff_until

    if schedule.mode in ("manual", "disabled"):
        return None

    if schedule.mode == "hourly":
        return (now + timedelta(hours=1)).isoformat()

    if schedule.mode == "daily":
        return (now + timedelta(days=1)).isoformat()

    if schedule.mode == "cron":
        if not schedule.cron_expression:
            raise ValueError("cron mode requires a cron_expression.")
        return compute_next_cron_run(schedule.cron_expression, now)

    return None


def compute_backoff_seconds(failure_count, base_seconds=60.0, max_seconds=3600.0):
    if failure_count <= 0:
        return 0.0
    return min(base_seconds * (2 ** (failure_count - 1)), max_seconds)


def record_run_outcome(schedule, success, now=None):
    """
    Returns a NEW ScheduleState reflecting the outcome of a run -
    never mutates the input. On failure, sets a backoff window and
    bumps failure_count; on success, clears both.
    """
    import dataclasses

    now = now or datetime.now(timezone.utc)

    if success:
        updated = dataclasses.replace(
            schedule, last_run=now.isoformat(), failure_count=0, backoff_until=None,
        )
    else:
        failure_count = schedule.failure_count + 1
        backoff_seconds = compute_backoff_seconds(failure_count)
        backoff_until = (now + timedelta(seconds=backoff_seconds)).isoformat()
        updated = dataclasses.replace(
            schedule, last_run=now.isoformat(), failure_count=failure_count,
            backoff_until=backoff_until,
        )

    updated.next_run = compute_next_run(updated, now)
    return updated
