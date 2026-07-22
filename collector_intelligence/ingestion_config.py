"""
Atlas v21 - Module 5: ingestion configuration.

Every numeric/behavioral threshold the ingestion framework uses lives
here so behavior can be tuned without touching adapter or pipeline
logic.
"""

from dataclasses import dataclass, field


@dataclass
class IngestionConfig:
    # If True, validation warnings are escalated to hard failures.
    strict_validation: bool = False

    # Whether ingest_source() may auto-detect an adapter when none is
    # explicitly given.
    allow_automatic_detection: bool = True

    # Minimum confidence gap between the best and second-best adapter
    # candidate required to NOT be considered ambiguous.
    adapter_ambiguity_threshold: float = 0.15

    # "skip": exact duplicates never reach successful_results.
    # "flag": duplicates are included but marked is_duplicate=True.
    # "allow": duplicate detection is skipped entirely.
    duplicate_policy: str = "skip"

    timestamp_formats: list = field(
        default_factory=lambda: ["iso8601", "date_only", "rfc2822"]
    )

    supported_currencies: set = field(
        default_factory=lambda: {
            "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CNY", "KRW",
        }
    )

    supported_url_schemes: set = field(
        default_factory=lambda: {"http", "https"}
    )

    max_content_length: int = 20000

    # "truncate": content beyond max_content_length is cut, with a
    # transformation record noting it. "reject": oversized content is
    # a hard validation error.
    oversized_content_policy: str = "truncate"

    # Whether to keep an untouched copy of the original payload inside
    # original_payload_metadata (bounded by max_content_length).
    preserve_raw_payload_snapshot: bool = True

    allow_recoverable_normalization: bool = True

    # "retain": unrecognized payload fields are kept in metadata.
    # "drop": unrecognized fields are discarded silently.
    # "warn": unrecognized fields are kept AND produce a warning.
    unknown_field_policy: str = "retain"

    # "retain_as_asking": an active/asking marketplace price is kept,
    # tagged clearly as not-sold evidence, never promoted to a sold
    # price no matter what.
    marketplace_asking_price_policy: str = "retain_as_asking"

    social_metadata_retention: bool = True

    # If False, one payload's build_raw_source() exception aborts the
    # whole batch instead of just failing that one record.
    batch_partial_success: bool = True

    max_nesting_depth: int = 6
