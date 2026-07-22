"""
Atlas v21 - Module 6: data models for the connector framework.

Every model is a plain dataclass with a to_dict() returning only
JSON-compatible primitives, lists, and dicts.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now():
    return datetime.now(timezone.utc).isoformat()


ERROR_TYPES = frozenset({
    "TIMEOUT", "NETWORK", "INVALID_CONTENT", "UNSUPPORTED_CONTENT_TYPE",
    "INVALID_RSS", "INVALID_XML", "INVALID_JSON", "OVERSIZED_PAYLOAD",
    "REDIRECT_LOOP", "SSL_FAILURE", "RATE_LIMITED", "TEMPORARY_FAILURE",
    "PERMANENT_FAILURE", "CONFIG_INVALID",
})

CHANGE_STATUSES = frozenset({
    "NEW", "UNCHANGED", "CHANGED", "REMOVED", "DUPLICATE", "TIMESTAMP_ONLY",
})


@dataclass
class ConnectorError:
    error_type: str
    message: str
    recoverable: bool = False
    status_code: int | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class FetchResult:
    success: bool
    url: str
    status_code: int | None = None
    body: str | None = None
    content_type: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    etag: str | None = None
    last_modified: str | None = None
    fetched_at: str = ""
    duration_ms: float = 0.0
    from_cache: bool = False
    not_modified: bool = False
    redirect_chain: list[str] = field(default_factory=list)
    attempts: int = 1
    error: ConnectorError | None = None

    def to_dict(self):
        return {
            "success": self.success,
            "url": self.url,
            "status_code": self.status_code,
            "body": self.body,
            "content_type": self.content_type,
            "headers": self.headers,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "fetched_at": self.fetched_at,
            "duration_ms": self.duration_ms,
            "from_cache": self.from_cache,
            "not_modified": self.not_modified,
            "redirect_chain": self.redirect_chain,
            "attempts": self.attempts,
            "error": self.error.to_dict() if self.error else None,
        }


@dataclass
class ChangeDetectionResult:
    status: str
    current_hash: str | None = None
    previous_hash: str | None = None
    current_fetched_at: str | None = None
    previous_fetched_at: str | None = None
    explanation: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class ConnectorHealth:
    connector_name: str
    healthy: bool
    checked_at: str = field(default_factory=utc_now)
    last_success_at: str | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class ScheduleState:
    mode: str = "manual"  # manual | hourly | daily | cron | disabled
    cron_expression: str | None = None
    next_run: str | None = None
    last_run: str | None = None
    failure_count: int = 0
    backoff_until: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ConnectorRunResult:
    connector_name: str
    success: bool
    fetch_result: FetchResult | None = None
    change_detection: ChangeDetectionResult | None = None
    ingestion_results: list[Any] = field(default_factory=list)  # Module 5 IngestionResult
    items_parsed: int = 0
    error: ConnectorError | None = None
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0

    def to_dict(self):
        return {
            "connector_name": self.connector_name,
            "success": self.success,
            "fetch_result": self.fetch_result.to_dict() if self.fetch_result else None,
            "change_detection": self.change_detection.to_dict() if self.change_detection else None,
            "ingestion_results": [
                r.to_dict() if hasattr(r, "to_dict") else r for r in self.ingestion_results
            ],
            "items_parsed": self.items_parsed,
            "error": self.error.to_dict() if self.error else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ConnectorBatchResult:
    results: list[ConnectorRunResult] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0

    def to_dict(self):
        return {
            "results": [r.to_dict() for r in self.results],
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_count": self.total_count,
        }
