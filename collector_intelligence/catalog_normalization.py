"""
Atlas v21 - Module 7: catalog normalization primitives.

Reuses Module 5's text/URL normalization where the concern overlaps
(whitespace, unicode, URL canonicalization) rather than reimplementing
it, and adds catalog-specific normalization (IDs, vocab canonicalization).
"""

import re

from collector_intelligence.catalog_models import (
    VALID_AUTHORITY_LEVELS,
    VALID_CATALOG_SOURCE_TYPES,
    VALID_CONNECTOR_NAMES,
    VALID_LIFECYCLE_STATES,
    VALID_PRIORITIES,
)
from collector_intelligence.connector_scheduler import VALID_MODES as VALID_SCHEDULE_MODES
from collector_intelligence.ingestion_normalization import clean_text, normalize_url

_ID_PATTERN = re.compile(r"[^a-z0-9_]+")


def normalize_id(value):
    """Deterministic canonical ID: lowercase, non-alnum -> underscore,
    collapsed, stripped."""
    if not value:
        return value
    text = str(value).strip().lower()
    text = _ID_PATTERN.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def normalize_text_field(value):
    if value is None:
        return None
    cleaned = clean_text(value)
    return cleaned or None


def normalize_tag(value):
    if not value:
        return None
    return normalize_id(value)


def normalize_tags(values):
    if not values:
        return []
    normalized = [normalize_tag(v) for v in values]
    seen = []
    for tag in normalized:
        if tag and tag not in seen:
            seen.append(tag)
    return seen


def normalize_alias(value):
    return normalize_text_field(value)


def normalize_aliases(values):
    if not values:
        return []
    normalized = [normalize_alias(v) for v in values]
    seen = []
    for alias in normalized:
        if alias and alias not in seen:
            seen.append(alias)
    return seen


def normalize_domain(value):
    if not value:
        return None
    domain = str(value).strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    return domain or None


def normalize_region(value):
    if not value:
        return None
    return str(value).strip().upper()


def normalize_language(value):
    if not value:
        return None
    return str(value).strip().lower()


def normalize_priority(value):
    """Returns (canonical_or_None, is_valid)."""
    if not value:
        return "medium", True
    text = str(value).strip().lower()
    return (text, True) if text in VALID_PRIORITIES else (value, False)


def normalize_lifecycle_state(value):
    if not value:
        return "proposed", True
    text = str(value).strip().lower()
    return (text, True) if text in VALID_LIFECYCLE_STATES else (value, False)


def normalize_authority_level(value):
    if not value:
        return "manual_untrusted", True
    text = str(value).strip().lower()
    return (text, True) if text in VALID_AUTHORITY_LEVELS else (value, False)


def normalize_catalog_source_type(value):
    if not value:
        return "manual_report", True
    text = str(value).strip().lower()
    return (text, True) if text in VALID_CATALOG_SOURCE_TYPES else (value, False)


def normalize_connector_name(value, allowed=None):
    if not value:
        return None, True
    text = str(value).strip().lower()
    allowed_set = allowed or VALID_CONNECTOR_NAMES
    return (text, True) if text in allowed_set else (value, False)


def normalize_schedule_mode(value):
    if not value:
        return "manual", True
    text = str(value).strip().lower()
    return (text, True) if text in VALID_SCHEDULE_MODES else (value, False)


def normalize_catalog_url(value, allowed_schemes=None):
    return normalize_url(value, allowed_schemes)


def normalize_connector_config_keys(config_dict):
    """Lower-cases and snake-cases config dict keys deterministically
    without touching values."""
    if not config_dict:
        return {}
    return {normalize_id(k): v for k, v in config_dict.items()}
