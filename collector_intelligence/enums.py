from enum import Enum


class PrimaryStrategy(str, Enum):
    FLIP_NOW = "FLIP_NOW"
    QUICK_FLIP = "QUICK_FLIP"
    HOLD_SHORT = "HOLD_SHORT"
    HOLD_MEDIUM = "HOLD_MEDIUM"
    HOLD_LONG = "HOLD_LONG"
    COLLECT_ONLY = "COLLECT_ONLY"
    WATCH = "WATCH"
    AVOID = "AVOID"


class Recommendation(str, Enum):
    CRITICAL_BUY = "CRITICAL_BUY"
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    CONDITIONAL_BUY = "CONDITIONAL_BUY"
    WATCH = "WATCH"
    SKIP = "SKIP"
    AVOID = "AVOID"


class AcquisitionDifficulty(str, Enum):
    EASY = "EASY"
    MODERATE = "MODERATE"
    HARD = "HARD"
    VERY_HARD = "VERY_HARD"
    EXTREME = "EXTREME"


class DemandDirection(str, Enum):
    FALLING = "FALLING"
    FLAT = "FLAT"
    RISING = "RISING"
    SURGING = "SURGING"
    UNKNOWN = "UNKNOWN"


class SourceType(str, Enum):
    OFFICIAL = "OFFICIAL"
    RETAILER = "RETAILER"
    PRESS_RELEASE = "PRESS_RELEASE"
    SOCIAL = "SOCIAL"
    COMMUNITY = "COMMUNITY"
    MARKETPLACE = "MARKETPLACE"
    NEWS = "NEWS"
    EVENT = "EVENT"
    OTHER = "OTHER"


# Status is intentionally left as free text rather than a closed
# enum - the mission spec describes these as examples, and new
# ecosystems (conventions, memberships, lotteries, etc.) are likely
# to need statuses not anticipated here. VALID_STATUSES exists for
# optional reference/validation, not enforcement.
VALID_STATUSES = frozenset({
    "rumored",
    "announced",
    "preorder",
    "lottery",
    "upcoming",
    "live",
    "low_stock",
    "sold_out",
    "restocked",
    "ended",
})


ENUM_FIELDS = {
    "primary_strategy": PrimaryStrategy,
    "recommendation": Recommendation,
    "acquisition_difficulty": AcquisitionDifficulty,
    "demand_direction": DemandDirection,
    "source_type": SourceType,
}


def coerce_enum_value(value, enum_cls, field_name):
    """
    Accepts None, an existing enum member, or a string matching one
    of the enum's values (case-insensitive). Returns the plain string
    .value (not the enum instance) so the model stays JSON/DB
    friendly, or None. Raises ValueError for anything else - an
    unrecognized strategy/recommendation/etc is a data bug worth
    surfacing, not silently swallowing.
    """
    if value is None:
        return None

    if isinstance(value, enum_cls):
        return value.value

    if isinstance(value, str):
        candidate = value.strip().upper()

        for member in enum_cls:
            if member.value == candidate:
                return member.value

    valid_values = ", ".join(
        member.value for member in enum_cls
    )

    raise ValueError(
        f"Invalid {field_name!r}: {value!r} is not one of "
        f"[{valid_values}]"
    )
