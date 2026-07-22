"""
Atlas v21 - Module 5: reusable payload validation primitives.

Every validator returns PayloadValidationError instances (or None) -
it never raises for bad payload data. Hard errors (severity="ERROR",
recoverable=False) block ingestion; warnings (severity="WARNING")
allow ingestion to proceed with the safest available interpretation.
"""

from collector_intelligence.ingestion_models import PayloadValidationError
from collector_intelligence.ingestion_normalization import (
    normalize_currency_code,
    normalize_source_type,
    normalize_timestamp,
    normalize_unit_scope,
    normalize_url,
    parse_decimal,
)


def error(field_name, code, message, recoverable=False):
    return PayloadValidationError(
        field_name=field_name, error_code=code, message=message,
        severity="ERROR", recoverable=recoverable,
    )


def warning(field_name, code, message, recoverable=True):
    return PayloadValidationError(
        field_name=field_name, error_code=code, message=message,
        severity="WARNING", recoverable=recoverable,
    )


def validate_required_fields(payload, field_names):
    issues = []
    for name in field_names:
        if not payload.get(name):
            issues.append(error(
                name, "MISSING_REQUIRED_FIELD",
                f"{name!r} is required and was missing or empty.",
            ))
    return issues


def validate_non_empty_content(title, body, field_label="title/body"):
    if not (title or "").strip() and not (body or "").strip():
        return [error(
            field_label, "EMPTY_CONTENT",
            "Both title and body/content were empty - there is no "
            "source text to analyze.",
        )]
    return []


def validate_url(value, field_name, config):
    if not value:
        return None, []

    normalized, is_valid = normalize_url(value, config.supported_url_schemes)

    if not is_valid:
        return None, [error(
            field_name, "INVALID_URL",
            f"{value!r} is not a valid URL with an allowed scheme "
            f"({sorted(config.supported_url_schemes)}).",
        )]

    return normalized, []


def validate_timestamp(value, field_name):
    if value is None or value == "":
        return None, []

    normalized, is_valid = normalize_timestamp(value)

    if not is_valid:
        return None, [warning(
            field_name, "UNPARSEABLE_TIMESTAMP",
            f"{field_name} value {value!r} could not be parsed as a "
            f"timestamp and was dropped.",
        )]

    return normalized, []


def validate_price(value, field_name):
    if value is None or value == "":
        return None, []

    parsed = parse_decimal(value)

    if parsed is None:
        return None, [error(
            field_name, "INVALID_NUMERIC",
            f"{field_name} value {value!r} is not a valid number.",
        )]

    if parsed < 0:
        return None, [error(
            field_name, "NEGATIVE_PRICE",
            f"{field_name} cannot be negative (got {parsed}).",
        )]

    return parsed, []


def validate_non_negative_quantity(value, field_name):
    if value is None or value == "":
        return None, []

    parsed = parse_decimal(value)

    if parsed is None:
        return None, [error(
            field_name, "INVALID_NUMERIC",
            f"{field_name} value {value!r} is not a valid number.",
        )]

    if parsed < 0:
        return None, [error(
            field_name, "NEGATIVE_QUANTITY",
            f"{field_name} cannot be negative (got {parsed}).",
        )]

    return int(round(parsed)), []


def validate_currency(value, field_name, config):
    if not value:
        return None, []

    code, is_supported = normalize_currency_code(value, config.supported_currencies)

    if not is_supported:
        return code, [warning(
            field_name, "UNSUPPORTED_CURRENCY",
            f"Currency {value!r} is not in the configured supported "
            f"set; kept as-is but unverified.",
        )]

    return code, []


def validate_source_type(value, field_name):
    if not value:
        return None, []

    normalized, is_valid = normalize_source_type(value)

    if not is_valid:
        return None, [warning(
            field_name, "UNRECOGNIZED_SOURCE_TYPE",
            f"{value!r} is not a recognized source type; left unset "
            f"rather than guessed.",
        )]

    return normalized, []


def validate_unit_scope(value, field_name):
    if not value:
        return None, []

    normalized, is_valid = normalize_unit_scope(value)

    if not is_valid:
        return None, [warning(
            field_name, "UNRECOGNIZED_UNIT_SCOPE",
            f"{value!r} is not a recognized unit scope; kept as "
            f"'unknown' rather than guessed.",
        )]

    return normalized, []


def validate_sold_status_combination(sold, sold_at):
    """
    "sold_at present while sold status is explicitly false" is
    incoherent - a timestamp with no sale.
    """
    if sold is False and sold_at:
        return [error(
            "sold_at", "INCOMPATIBLE_SOLD_STATUS",
            "sold_at was provided but sold is explicitly false - a "
            "sale timestamp with no sale is contradictory.",
        )]
    return []


def validate_grading_combination(graded, grade, grading_company):
    if graded is False and (grade or grading_company):
        return [error(
            "grade", "INCOMPATIBLE_GRADING_STATUS",
            "A grade/grading company was provided but graded is "
            "explicitly false.",
        )]
    return []


def validate_event_dates(event_start, event_end):
    if event_start and event_end and event_start > event_end:
        return [error(
            "event_end", "EVENT_END_BEFORE_START",
            f"event_end ({event_end}) is before event_start "
            f"({event_start}).",
        )]
    return []


def validate_content_length(text, field_name, config):
    """
    Returns (possibly-truncated text, issues). Truncation policy is
    config-driven; a rejection is a hard error, a truncation is a
    recoverable warning.
    """
    if not text or len(text) <= config.max_content_length:
        return text, []

    if config.oversized_content_policy == "reject":
        return text, [error(
            field_name, "CONTENT_TOO_LARGE",
            f"{field_name} is {len(text)} characters, exceeding the "
            f"configured maximum of {config.max_content_length}.",
        )]

    truncated = text[: config.max_content_length]
    return truncated, [warning(
        field_name, "CONTENT_TRUNCATED",
        f"{field_name} was truncated from {len(text)} to "
        f"{config.max_content_length} characters.",
    )]
