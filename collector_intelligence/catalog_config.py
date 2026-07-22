"""
Atlas v21 - Module 7: catalog configuration.

Every numeric/behavioral threshold the catalog loader/validator uses
lives here.
"""

import re
from dataclasses import dataclass, field


DEFAULT_SECRET_KEY_PATTERNS = (
    r"api[_-]?key", r"secret", r"token", r"password", r"passwd",
    r"bearer", r"authorization", r"auth[_-]?header", r"cookie",
    r"private[_-]?key", r"access[_-]?key",
)


@dataclass
class CatalogConfig:
    strict_validation: bool = False
    allow_unknown_fields: bool = True
    allow_duplicate_canonical_urls: bool = False

    allowed_url_schemes: frozenset = field(
        default_factory=lambda: frozenset({"http", "https"})
    )
    allowed_connector_names: frozenset = field(default_factory=frozenset)  # empty = use catalog_models default set
    allowed_regions: frozenset = field(default_factory=frozenset)  # empty = unrestricted
    allowed_languages: frozenset = field(default_factory=frozenset)  # empty = unrestricted

    normalize_ids: bool = True
    preserve_input_snapshot: bool = True

    maximum_catalog_size_bytes: int = 2_000_000
    maximum_sources: int = 5000
    maximum_scouts: int = 500
    maximum_metadata_depth: int = 6

    secret_key_patterns: tuple = DEFAULT_SECRET_KEY_PATTERNS

    treat_warnings_as_errors: bool = False
    allow_proposed_sources_in_plan: bool = False

    # "run_with_warning" | "exclude" - how deprecated sources behave
    # in an execution plan.
    deprecated_source_policy: str = "run_with_warning"

    fingerprint_algorithm: str = "sha256"

    def compiled_secret_patterns(self):
        return [re.compile(p, re.IGNORECASE) for p in self.secret_key_patterns]
