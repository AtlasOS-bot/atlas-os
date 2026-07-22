"""
Atlas v21 - Module 5: data models for the source ingestion framework.

Every model here is a plain dataclass with a to_dict() that returns
only JSON-compatible primitives, lists, and dicts.
"""

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class IngestionContext:
    received_at: str = field(default_factory=_utc_now)
    collector_name: str | None = None
    batch_id: str | None = None
    correlation_id: str | None = None
    dry_run: bool = False
    environment: str = "development"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class TransformationRecord:
    field_name: str
    original_value: Any
    normalized_value: Any
    transformation_type: str
    explanation: str

    def to_dict(self):
        return asdict(self)


@dataclass
class PayloadValidationError:
    field_name: str
    error_code: str
    message: str
    severity: str = "ERROR"  # "ERROR" | "WARNING"
    recoverable: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class AdapterDetection:
    adapter_name: str | None
    confidence: float
    reasons: list[str] = field(default_factory=list)
    ambiguous: bool = False
    alternatives: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class IngestionResult:
    success: bool
    raw_source: Any = None  # RawSourceInput | None

    adapter_name: str | None = None
    adapter_version: str | None = None
    detected_source_type: str | None = None
    payload_fingerprint: str | None = None
    identity_key: str | None = None

    validation_errors: list[PayloadValidationError] = field(default_factory=list)
    validation_warnings: list[PayloadValidationError] = field(default_factory=list)
    transformations: list[TransformationRecord] = field(default_factory=list)
    original_payload_metadata: dict[str, Any] = field(default_factory=dict)

    ingestion_started_at: str = ""
    ingestion_completed_at: str = ""
    duration_ms: float = 0.0

    requires_manual_review: bool = False
    manual_review_reasons: list[str] = field(default_factory=list)

    # Batch-level bookkeeping, filled in by ingest_batch().
    is_duplicate: bool = False
    duplicate_of: str | None = None
    dry_run: bool = False

    def to_dict(self):
        return {
            "success": self.success,
            "raw_source": self.raw_source.to_dict() if hasattr(self.raw_source, "to_dict") else self.raw_source,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "detected_source_type": self.detected_source_type,
            "payload_fingerprint": self.payload_fingerprint,
            "identity_key": self.identity_key,
            "validation_errors": [e.to_dict() for e in self.validation_errors],
            "validation_warnings": [w.to_dict() for w in self.validation_warnings],
            "transformations": [t.to_dict() for t in self.transformations],
            "original_payload_metadata": self.original_payload_metadata,
            "ingestion_started_at": self.ingestion_started_at,
            "ingestion_completed_at": self.ingestion_completed_at,
            "duration_ms": self.duration_ms,
            "requires_manual_review": self.requires_manual_review,
            "manual_review_reasons": self.manual_review_reasons,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
            "dry_run": self.dry_run,
        }


@dataclass
class IngestionBatchResult:
    results: list[IngestionResult] = field(default_factory=list)
    successful_results: list[IngestionResult] = field(default_factory=list)
    failed_results: list[IngestionResult] = field(default_factory=list)
    duplicate_results: list[IngestionResult] = field(default_factory=list)

    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    duplicate_count: int = 0

    warnings: list[str] = field(default_factory=list)
    batch_id: str | None = None

    def to_dict(self):
        return {
            "results": [r.to_dict() for r in self.results],
            "successful_results": [r.to_dict() for r in self.successful_results],
            "failed_results": [r.to_dict() for r in self.failed_results],
            "duplicate_results": [r.to_dict() for r in self.duplicate_results],
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "duplicate_count": self.duplicate_count,
            "warnings": self.warnings,
            "batch_id": self.batch_id,
        }
