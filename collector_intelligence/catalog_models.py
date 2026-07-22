"""
Atlas v21 - Module 7: source catalog data models.

The catalog describes WHAT Atlas watches, WHY, and HOW OFTEN - never
HOW to fetch it (that's Module 6) or how to score it (Module 3).
Nothing here imports scoring/finalization logic.

Every model is a plain dataclass with a to_dict() returning only
JSON-compatible primitives, lists, and dicts, so a whole catalog is
always safely serializable regardless of input key order.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from collector_intelligence.connector_scheduler import VALID_MODES as VALID_SCHEDULE_MODES


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------

VALID_PRIORITIES = ("critical", "high", "medium", "low", "archival")

VALID_LIFECYCLE_STATES = (
    "proposed", "active", "paused", "deprecated", "retired", "broken",
)

VALID_AUTHORITY_LEVELS = (
    "official_primary", "official_secondary", "authorized_retailer",
    "reputable_press", "marketplace_confirmed_sale", "marketplace_asking",
    "community_verified", "community_unverified", "social_verified",
    "social_unverified", "manual_trusted", "manual_untrusted",
)

# Catalog-level source types - a different, more granular axis than
# Module 1's SourceType (which describes evidence provenance for
# scoring). This describes what KIND of retrievable thing a source
# is, for catalog bookkeeping and connector-compatibility validation.
VALID_CATALOG_SOURCE_TYPES = (
    "official_announcement", "official_product_page", "official_news",
    "retailer_product_page", "retailer_category_page", "press_release",
    "event_listing", "convention_announcement", "rss_feed", "atom_feed",
    "json_feed", "xml_feed", "marketplace_export", "marketplace_sold_data",
    "marketplace_asking_data", "community_post", "social_post", "manual_report",
)

VALID_HEALTH_STATUSES = (
    "healthy", "warning", "failing", "stale", "disabled", "unknown",
)

VALID_RECOMMENDED_ACTIONS = (
    "none", "retry", "inspect", "pause", "replace", "retire",
)

VALID_CONNECTOR_NAMES = (
    "rss_connector", "html_connector", "json_connector", "xml_connector",
    "announcement_connector", "retailer_page_connector", "event_connector",
)

PRIORITY_RANK = {name: rank for rank, name in enumerate(VALID_PRIORITIES)}
AUTHORITY_RANK = {name: rank for rank, name in enumerate(VALID_AUTHORITY_LEVELS)}


# ---------------------------------------------------------------
# Small supporting models
# ---------------------------------------------------------------

@dataclass
class ScheduleSpec:
    """None fields mean "not set at this level" - inheritance fills
    them in from scout/catalog defaults."""
    mode: str | None = None
    cron_expression: str | None = None

    def to_dict(self):
        return asdict(self)

    def is_empty(self):
        return self.mode is None and self.cron_expression is None


@dataclass
class ExpectedEvidenceDefinition:
    evidence_types: list[str] = field(default_factory=list)
    likely_fields: list[str] = field(default_factory=list)
    official_status: str | None = None
    price_kind: str | None = None
    expected_unit_scope: str | None = None
    supports_release_date: bool = False
    supports_availability: bool = False
    supports_purchase_limits: bool = False
    supports_market_price: bool = False
    supports_event_details: bool = False
    notes: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class SourceHealthPolicy:
    max_consecutive_failures: int = 5
    disable_after_failures: int = 10
    stale_after: float = 168.0  # hours
    warning_after: float = 48.0  # hours
    expected_update_frequency: str | None = None
    temporary_failure_backoff: str = "exponential"
    permanent_failure_action: str = "pause"

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------
# Catalog entities
# ---------------------------------------------------------------

@dataclass
class CategoryDefinition:
    category_id: str
    name: str
    parent_category_id: str | None = None
    description: str | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class BrandDefinition:
    brand_id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    official_domains: list[str] = field(default_factory=list)
    region: str | None = None
    enabled: bool = True
    priority: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class ScoutDefinition:
    scout_id: str
    name: str
    description: str | None = None
    enabled: bool = True
    priority: str = "medium"
    categories: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    default_schedule: ScheduleSpec = field(default_factory=ScheduleSpec)
    default_connector_config: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    owner: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        return data


@dataclass
class SourceDefinition:
    source_id: str
    name: str
    enabled: bool = True
    source_type: str = "manual_report"
    authority_level: str = "manual_untrusted"
    connector_type: str | None = None
    connector_version: str | None = None
    url: str | None = None
    brand_id: str | None = None
    scout_ids: list[str] = field(default_factory=list)
    category_ids: list[str] = field(default_factory=list)
    schedule: ScheduleSpec = field(default_factory=ScheduleSpec)
    connector_config: dict[str, Any] = field(default_factory=dict)
    expected_evidence: ExpectedEvidenceDefinition = field(
        default_factory=ExpectedEvidenceDefinition
    )
    region: str | None = None
    language: str | None = None
    lifecycle_state: str = "proposed"
    health_policy: SourceHealthPolicy = field(default_factory=SourceHealthPolicy)
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class SourceCatalog:
    catalog_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    generated_at: str = field(default_factory=utc_now)
    environment: str = "development"
    scouts: dict[str, ScoutDefinition] = field(default_factory=dict)
    brands: dict[str, BrandDefinition] = field(default_factory=dict)
    sources: dict[str, SourceDefinition] = field(default_factory=dict)
    categories: dict[str, CategoryDefinition] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "catalog_version": self.catalog_version,
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "environment": self.environment,
            "scouts": {k: v.to_dict() for k, v in sorted(self.scouts.items())},
            "brands": {k: v.to_dict() for k, v in sorted(self.brands.items())},
            "sources": {k: v.to_dict() for k, v in sorted(self.sources.items())},
            "categories": {k: v.to_dict() for k, v in sorted(self.categories.items())},
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------
# Validation
# ---------------------------------------------------------------

@dataclass
class CatalogValidationIssue:
    path: str
    error_code: str
    message: str
    severity: str = "ERROR"
    recoverable: bool = False
    suggested_fix: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class CatalogValidationResult:
    valid: bool
    errors: list[CatalogValidationIssue] = field(default_factory=list)
    warnings: list[CatalogValidationIssue] = field(default_factory=list)
    normalized_catalog: SourceCatalog | None = None
    source_count: int = 0
    scout_count: int = 0
    brand_count: int = 0
    category_count: int = 0

    def to_dict(self):
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "normalized_catalog": self.normalized_catalog.to_dict() if self.normalized_catalog else None,
            "source_count": self.source_count,
            "scout_count": self.scout_count,
            "brand_count": self.brand_count,
            "category_count": self.category_count,
        }


# ---------------------------------------------------------------
# Execution planning
# ---------------------------------------------------------------

@dataclass
class ConnectorExecutionItem:
    scout_id: str
    source_id: str
    connector_name: str | None
    source_url: str | None
    schedule: dict[str, Any]
    connector_config: dict[str, Any]
    authority_level: str
    expected_evidence: dict[str, Any]
    priority: str
    due: bool
    due_reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class ConnectorExecutionPlan:
    generated_at: str = field(default_factory=utc_now)
    items: list[ConnectorExecutionItem] = field(default_factory=list)
    due_items: list[ConnectorExecutionItem] = field(default_factory=list)
    skipped_items: list[ConnectorExecutionItem] = field(default_factory=list)
    disabled_items: list[dict[str, Any]] = field(default_factory=list)
    invalid_items: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "generated_at": self.generated_at,
            "items": [i.to_dict() for i in self.items],
            "due_items": [i.to_dict() for i in self.due_items],
            "skipped_items": [i.to_dict() for i in self.skipped_items],
            "disabled_items": self.disabled_items,
            "invalid_items": self.invalid_items,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------
# Snapshot / diff / health
# ---------------------------------------------------------------

@dataclass
class CatalogSnapshot:
    fingerprint: str
    created_at: str = field(default_factory=utc_now)
    catalog_version: str = ""
    source_count: int = 0
    scout_count: int = 0
    brand_count: int = 0
    normalized_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class CatalogDiff:
    added_sources: list[str] = field(default_factory=list)
    removed_sources: list[str] = field(default_factory=list)
    changed_sources: list[dict[str, Any]] = field(default_factory=list)
    enabled_sources: list[str] = field(default_factory=list)
    disabled_sources: list[str] = field(default_factory=list)
    changed_scouts: list[dict[str, Any]] = field(default_factory=list)
    changed_brands: list[dict[str, Any]] = field(default_factory=list)
    changed_schedules: list[dict[str, Any]] = field(default_factory=list)
    changed_connector_configs: list[dict[str, Any]] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class SourceHealthState:
    source_id: str
    last_success_at: str | None = None
    last_failure_at: str | None = None
    consecutive_failures: int = 0
    last_error_code: str | None = None
    last_change_detected_at: str | None = None
    stale_since: str | None = None
    health_status: str = "unknown"
    recommended_catalog_action: str = "none"

    def to_dict(self):
        return asdict(self)
