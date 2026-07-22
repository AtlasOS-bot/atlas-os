"""
Atlas v21 - Module 5: the source adapter interface.

Every adapter converts one source-specific payload shape into a
Module 2 RawSourceInput. Adapters do ONE job: faithful, deterministic
translation. They never score, recommend, merge, fetch, persist, or
mutate the caller's payload.

Subclasses implement the five payload-specific hooks (can_handle,
validate, transform, extract_metadata, fingerprint); ingest() here
orchestrates them identically for every adapter so behavior (security
precheck, content-length limits, untrusted-content marking, timing,
error handling) is consistent across the whole registry.
"""

import copy
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_models import (
    IngestionResult,
    PayloadValidationError,
    TransformationRecord,
)
from collector_intelligence.source_models import RawSourceInput


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class PayloadTooDeepError(Exception):
    pass


def _measure_depth(value, current=0):
    if current > 50:  # absolute safety ceiling regardless of config
        raise PayloadTooDeepError()

    if isinstance(value, dict):
        if not value:
            return current
        return max(_measure_depth(v, current + 1) for v in value.values())

    if isinstance(value, (list, tuple)):
        if not value:
            return current
        return max(_measure_depth(v, current + 1) for v in value)

    return current


class SourceAdapter(ABC):
    name: str = "base"
    version: str = "1.0.0"
    supported_payload_types: tuple = (dict,)
    supported_source_types: tuple = ()

    # --- Subclasses implement these ---

    @abstractmethod
    def can_handle(self, payload) -> bool:
        ...

    def detection_confidence(self, payload):
        """
        Returns (confidence 0-1, reasons). Default: moderate flat
        confidence when can_handle() matches. Adapters with more
        specific payload shapes should override this to score higher
        when their distinguishing fields are present, so the registry
        can prefer a specific adapter over a generic catch-all.
        """
        if self.can_handle(payload):
            return 0.5, [f"{self.name}.can_handle() matched"]
        return 0.0, []

    @abstractmethod
    def validate(self, payload, config):
        """Returns (errors, warnings) - lists of PayloadValidationError."""
        ...

    @abstractmethod
    def transform(self, payload, context, config):
        """
        Returns (fields, transformations) where `fields` is a dict
        with keys drawn from RawSourceInput's own fields (title, body,
        source_name, source_type, source_url, published_at, author,
        retailer, brand_hint, franchise_hint) - built deterministically
        from the payload, never inventing prose that wasn't supplied.
        """
        ...

    @abstractmethod
    def extract_metadata(self, payload):
        """Returns a JSON-compatible dict of adapter-specific details."""
        ...

    def fingerprint(self, payload):
        """
        Default: title/content-based fingerprint. Adapters with a
        real identity field (URL, GUID, listing ID) should override
        this to pass it through so duplicate detection is accurate.
        """
        text = payload if isinstance(payload, str) else str(payload.get("body") or payload.get("content") or "")
        title = None if isinstance(payload, str) else payload.get("title")
        return compute_fingerprint(title=title, content=text)

    def describe(self):
        return {
            "name": self.name,
            "version": self.version,
            "supported_payload_types": [t.__name__ for t in self.supported_payload_types],
            "supported_source_types": list(self.supported_source_types),
        }

    # --- Orchestration (shared by every adapter) ---

    def ingest(self, payload, context, config):
        started = _utc_now()
        start_perf = time.perf_counter()

        errors = []
        warnings = []
        transformations = []
        manual_review_reasons = []

        if not isinstance(payload, self.supported_payload_types):
            errors.append(PayloadValidationError(
                field_name="payload",
                error_code="UNSUPPORTED_PAYLOAD_TYPE",
                message=(
                    f"{self.name} expects one of "
                    f"{[t.__name__ for t in self.supported_payload_types]}, "
                    f"got {type(payload).__name__}."
                ),
                severity="ERROR",
                recoverable=False,
            ))
            return self._failure_result(
                started, start_perf, errors, warnings, manual_review_reasons,
            )

        try:
            depth = _measure_depth(payload)
        except PayloadTooDeepError:
            depth = None
            errors.append(PayloadValidationError(
                field_name="payload",
                error_code="PAYLOAD_TOO_DEEP",
                message="Payload nesting exceeds the absolute safety ceiling.",
                severity="ERROR",
                recoverable=False,
            ))

        if depth is not None and depth > config.max_nesting_depth:
            errors.append(PayloadValidationError(
                field_name="payload",
                error_code="PAYLOAD_TOO_DEEP",
                message=(
                    f"Payload nesting depth {depth} exceeds the configured "
                    f"maximum of {config.max_nesting_depth}."
                ),
                severity="ERROR",
                recoverable=False,
            ))

        if errors:
            return self._failure_result(
                started, start_perf, errors, warnings, manual_review_reasons,
            )

        # Never let the adapter see (or accidentally mutate) the
        # caller's own object.
        safe_payload = copy.deepcopy(payload)

        adapter_errors, adapter_warnings = self.validate(safe_payload, config)
        errors.extend(adapter_errors)

        if config.strict_validation and adapter_warnings:
            # Promote warnings to hard errors (as their own copies, with
            # severity flipped) rather than silently proceeding.
            for w in adapter_warnings:
                errors.append(PayloadValidationError(
                    field_name=w.field_name,
                    error_code=w.error_code,
                    message=f"(strict mode) {w.message}",
                    severity="ERROR",
                    recoverable=False,
                ))
        else:
            warnings.extend(adapter_warnings)

        if errors:
            return self._failure_result(
                started, start_perf, errors, warnings, manual_review_reasons,
                metadata=self._safe_extract_metadata(safe_payload),
            )

        fields, field_transformations = self.transform(safe_payload, context, config)
        transformations.extend(field_transformations)

        from collector_intelligence.ingestion_validation import validate_content_length

        body_text, length_issues = validate_content_length(
            fields.get("body"), "body", config,
        )
        length_errors = [i for i in length_issues if i.severity == "ERROR"]

        if length_errors:
            errors.extend(length_errors)
            return self._failure_result(
                started, start_perf, errors, warnings, manual_review_reasons,
                metadata=self._safe_extract_metadata(safe_payload),
            )

        if body_text != fields.get("body"):
            transformations.append(record_transformation(
                "body", fields.get("body"), body_text, "content_truncated",
                f"Body exceeded the configured max_content_length "
                f"({config.max_content_length}) and was truncated.",
            ))
            fields = dict(fields)
            fields["body"] = body_text

        warnings.extend(i for i in length_issues if i.severity == "WARNING")

        metadata = self.extract_metadata(safe_payload)
        metadata["content_trust"] = "untrusted_external_input"
        metadata["ingested_via_adapter"] = self.name
        metadata["adapter_version"] = self.version

        if config.preserve_raw_payload_snapshot:
            snapshot = safe_payload if isinstance(safe_payload, str) else dict(safe_payload)
            metadata["original_payload_snapshot"] = _bounded_snapshot(
                snapshot, config.max_content_length,
            )

        identity_key, content_hash, combined_fingerprint = self.fingerprint(safe_payload)

        raw_source = RawSourceInput(
            title=fields.get("title") or "",
            body=fields.get("body") or "",
            source_name=fields.get("source_name"),
            source_type=fields.get("source_type"),
            source_url=fields.get("source_url"),
            published_at=fields.get("published_at"),
            author=fields.get("author"),
            retailer=fields.get("retailer"),
            brand_hint=fields.get("brand_hint"),
            franchise_hint=fields.get("franchise_hint"),
            raw_metadata=metadata,
        )

        if warnings and not manual_review_reasons:
            unresolved = [w for w in warnings if w.error_code in {
                "UNRECOGNIZED_SOURCE_TYPE", "UNRECOGNIZED_UNIT_SCOPE",
                "UNSUPPORTED_CURRENCY",
            }]
            if unresolved:
                manual_review_reasons = [
                    f"{w.field_name}: {w.message}" for w in unresolved
                ]

        completed = _utc_now()
        duration_ms = (time.perf_counter() - start_perf) * 1000

        return IngestionResult(
            success=True,
            raw_source=raw_source,
            adapter_name=self.name,
            adapter_version=self.version,
            detected_source_type=fields.get("source_type"),
            payload_fingerprint=combined_fingerprint,
            identity_key=identity_key,
            validation_errors=[],
            validation_warnings=warnings,
            transformations=transformations,
            original_payload_metadata={"payload_type": type(payload).__name__},
            ingestion_started_at=started,
            ingestion_completed_at=completed,
            duration_ms=round(duration_ms, 3),
            requires_manual_review=bool(manual_review_reasons),
            manual_review_reasons=manual_review_reasons,
            dry_run=context.dry_run if context else False,
        )

    def _safe_extract_metadata(self, safe_payload):
        try:
            return self.extract_metadata(safe_payload)
        except Exception:
            return {}

    def _failure_result(
        self, started, start_perf, errors, warnings, manual_review_reasons,
        metadata=None,
    ):
        completed = _utc_now()
        duration_ms = (time.perf_counter() - start_perf) * 1000

        return IngestionResult(
            success=False,
            raw_source=None,
            adapter_name=self.name,
            adapter_version=self.version,
            validation_errors=errors,
            validation_warnings=warnings,
            original_payload_metadata=metadata or {},
            ingestion_started_at=started,
            ingestion_completed_at=completed,
            duration_ms=round(duration_ms, 3),
            requires_manual_review=True,
            manual_review_reasons=[e.message for e in errors],
        )


def _bounded_snapshot(payload, max_length):
    if isinstance(payload, str):
        return payload[:max_length]

    bounded = {}
    for key, value in payload.items():
        if isinstance(value, str):
            bounded[key] = value[:max_length]
        else:
            bounded[key] = value
    return bounded


def record_transformation(field_name, original, normalized, transformation_type, explanation):
    return TransformationRecord(
        field_name=field_name,
        original_value=original,
        normalized_value=normalized,
        transformation_type=transformation_type,
        explanation=explanation,
    )
