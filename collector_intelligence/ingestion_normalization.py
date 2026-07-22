"""
Atlas v21 - Module 5: normalization primitives.

Normalizes without destroying original evidence - every function here
returns a cleaned value, never silently reinterprets meaning (an
asking price is never turned into a sold price, a rumor is never
turned into a confirmed fact, etc.). Callers that need to know
whether normalization changed something should compare the input to
the output themselves and record a TransformationRecord.
"""

import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from collector_intelligence.enums import SourceType
from collector_intelligence.evidence_ledger import UNIT_SCOPE_KEYWORDS

CONTROL_CHAR_PATTERN = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_HTML_SCRIPT_STYLE_PATTERN = re.compile(
    r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_HTML_ENTITY_MAP = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
    "&#39;": "'", "&apos;": "'", "&nbsp;": " ",
}

_TRUE_STRINGS = {"true", "yes", "y", "1", "sold", "active", "confirmed", "verified"}
_FALSE_STRINGS = {"false", "no", "n", "0", "unsold", "inactive", "unconfirmed", "unverified"}


def strip_control_characters(text):
    if not isinstance(text, str):
        return text
    return CONTROL_CHAR_PATTERN.sub("", text)


def normalize_unicode(text):
    if not isinstance(text, str):
        return text
    return unicodedata.normalize("NFKC", text)


def normalize_whitespace(text):
    if not isinstance(text, str):
        return text
    collapsed = re.sub(r"[ \t\f\v]+", " ", text)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def html_to_text(value):
    """
    Strips script/style blocks entirely (never executed, never kept),
    strips remaining tags, and unescapes a small set of common
    entities. Returns (text, was_html) so callers can record that a
    transformation happened.
    """
    if not isinstance(value, str):
        return value, False

    if "<" not in value or ">" not in value:
        return value, False

    without_scripts = _HTML_SCRIPT_STYLE_PATTERN.sub(" ", value)
    without_tags = _HTML_TAG_PATTERN.sub(" ", without_scripts)

    for entity, replacement in _HTML_ENTITY_MAP.items():
        without_tags = without_tags.replace(entity, replacement)

    return normalize_whitespace(without_tags), without_tags != value


def clean_text(value):
    """Full text cleanup pipeline: control chars -> unicode -> whitespace."""
    if not isinstance(value, str):
        return value
    return normalize_whitespace(normalize_unicode(strip_control_characters(value)))


def normalize_url(url, allowed_schemes=None):
    """
    Returns (normalized_url, is_valid). A URL is only considered valid
    if it parses with an allowed scheme and a network location.
    """
    if not url or not isinstance(url, str):
        return url, False

    allowed_schemes = allowed_schemes or {"http", "https"}
    candidate = url.strip()

    try:
        parts = urlsplit(candidate)
    except ValueError:
        return url, False

    if parts.scheme.lower() not in allowed_schemes or not parts.netloc:
        return url, False

    normalized = urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path or "",
        parts.query,
        "",  # drop fragment - not part of canonical identity
    ))

    return normalized, True


def normalize_source_name(name):
    if not name or not isinstance(name, str):
        return None
    return normalize_whitespace(name) or None


def normalize_currency_code(value, supported=None):
    """Returns (code, is_supported). Accepts symbols for common currencies."""
    if not value:
        return None, True

    symbol_map = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}

    if value in symbol_map:
        code = symbol_map[value]
    else:
        code = str(value).strip().upper()

    supported = supported or {"USD", "EUR", "GBP", "JPY", "CAD", "AUD"}
    return code, code in supported


_ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def normalize_timestamp(value):
    """
    Returns (iso_string, is_valid). None input is valid-but-empty
    (nothing to normalize). Unparseable non-empty input is invalid.
    """
    if value is None or value == "":
        return None, True

    if isinstance(value, datetime):
        return value.isoformat(), True

    if not isinstance(value, str):
        return value, False

    text = value.strip()

    for fmt in _ISO_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.isoformat(), True
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.isoformat(), True
    except ValueError:
        return value, False


def parse_decimal(value):
    """Returns a float or None - never raises."""
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.\-]", "", value)
        if not cleaned or cleaned in {"-", "."}:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def parse_quantity(value):
    """Returns a non-negative int or None - never raises."""
    parsed = parse_decimal(value)
    if parsed is None:
        return None
    quantity = int(round(parsed))
    return quantity if quantity >= 0 else None


def parse_boolean(value):
    """Returns True/False/None (None = genuinely unknown, not False)."""
    if isinstance(value, bool):
        return value

    if value is None:
        return None

    text = str(value).strip().lower()

    if text in _TRUE_STRINGS:
        return True
    if text in _FALSE_STRINGS:
        return False

    return None


_SOURCE_TYPE_ALIASES = {
    "official": "OFFICIAL",
    "brand": "OFFICIAL",
    "retailer": "RETAILER",
    "store": "RETAILER",
    "press_release": "PRESS_RELEASE",
    "press release": "PRESS_RELEASE",
    "pr": "PRESS_RELEASE",
    "social": "SOCIAL",
    "social_media": "SOCIAL",
    "community": "COMMUNITY",
    "forum": "COMMUNITY",
    "marketplace": "MARKETPLACE",
    "resale": "MARKETPLACE",
    "news": "NEWS",
    "article": "NEWS",
    "event": "EVENT",
    "convention": "EVENT",
    "other": "OTHER",
}

_VALID_SOURCE_TYPES = {member.value for member in SourceType}


def normalize_source_type(value):
    """Returns (canonical_value_or_None, is_valid)."""
    if not value:
        return None, True

    text = str(value).strip()

    if text.upper() in _VALID_SOURCE_TYPES:
        return text.upper(), True

    alias = _SOURCE_TYPE_ALIASES.get(text.lower())
    if alias:
        return alias, True

    return text, False


_VALID_UNIT_SCOPES = {scope for scope, _ in UNIT_SCOPE_KEYWORDS} | {"unknown"}

_UNIT_SCOPE_ALIASES = {
    "single": "single_item",
    "item": "single_item",
    "unit": "single_item",
    "individual": "single_item",
    "sealed box": "box",
    "booster box": "box",
    "sealed case": "case",
    "complete set": "complete_set",
    "full set": "complete_set",
    "set": "complete_set",
}


def normalize_unit_scope(value):
    """Returns (canonical_value_or_None, is_valid)."""
    if not value:
        return None, True

    text = str(value).strip().lower().replace(" ", "_")

    if text in _VALID_UNIT_SCOPES:
        return text, True

    alias = _UNIT_SCOPE_ALIASES.get(str(value).strip().lower())
    if alias:
        return alias, True

    return value, False


def normalize_platform_name(value):
    if not value or not isinstance(value, str):
        return None
    return normalize_whitespace(value).strip().title() or None
