"""
Atlas v21 - Module 6: the connector interface.

A Connector retrieves and normalizes data - nothing more. It never
scores, recommends, merges opportunities, or writes to a database;
those are Modules 2-4's jobs. run() orchestrates fetch -> change
detection -> parse -> normalize -> build_ingestion_payload() into a
list of (payload, adapter_name) pairs ready for Module 5.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from collector_intelligence.connector_models import (
    ChangeDetectionResult,
    ConnectorError,
    ConnectorHealth,
    ConnectorRunResult,
    FetchResult,
)
from collector_intelligence.connector_cache import CacheEntry, compute_content_hash
from collector_intelligence.change_detection import detect_change


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class Connector(ABC):
    name: str = "base_connector"
    version: str = "1.0.0"
    supported_source_types: tuple = ()

    @abstractmethod
    def supports(self, source_descriptor):
        """True if this connector can handle `source_descriptor` (a
        dict describing what to fetch - at minimum a `url`)."""
        ...

    def validate_config(self, source_descriptor, config):
        """Returns a list of ConnectorError. Base implementation just
        requires a URL; subclasses add their own required fields."""
        if not source_descriptor.get("url"):
            return [ConnectorError(
                error_type="CONFIG_INVALID",
                message=f"{self.name} requires a 'url' in the source descriptor.",
                recoverable=False,
            )]
        return []

    def fetch(self, source_descriptor, http_client, cache, config):
        url = source_descriptor["url"]
        cached = cache.get(url) if config.use_etag or config.use_last_modified else None

        result = http_client.get(
            url, config,
            etag=cached.etag if cached else None,
            last_modified=cached.last_modified if cached else None,
        )

        if result.not_modified and cached is not None:
            # Server confirmed nothing changed - reuse the cached body
            # for parsing/change-detection purposes.
            result.body = cached.body
            result.content_type = cached.content_type

        return result

    @abstractmethod
    def parse(self, fetch_result, source_descriptor):
        """Returns a list of parsed items (even if just one).
        `source_descriptor` is available for connectors (JSON/XML)
        whose item shape depends on descriptor-level configuration
        (e.g. an `items_path`)."""
        ...

    @abstractmethod
    def normalize(self, parsed_item, source_descriptor):
        """Returns a plain dict of normalized fields for one item."""
        ...

    @abstractmethod
    def build_ingestion_payload(self, normalized_item, source_descriptor):
        """Returns (payload, adapter_name) for Module 5's ingest_source()."""
        ...

    def health_check(self, http_client, config, source_descriptor=None):
        if source_descriptor is None:
            return ConnectorHealth(
                connector_name=self.name, healthy=True,
                details={"note": "No source descriptor supplied - static check only."},
            )

        result = http_client.get(source_descriptor["url"], config)

        return ConnectorHealth(
            connector_name=self.name,
            healthy=result.success,
            last_success_at=_utc_now() if result.success else None,
            consecutive_failures=0 if result.success else 1,
            last_error=result.error.message if result.error else None,
            details={"status_code": result.status_code},
        )

    def describe(self):
        return {
            "name": self.name,
            "version": self.version,
            "supported_source_types": list(self.supported_source_types),
        }

    def run(self, source_descriptor, http_client, cache, config, ingest_fn):
        """
        Full orchestration: fetch -> change detection -> parse ->
        normalize -> build payloads -> ingest via Module 5's
        ingest_fn(payload, adapter_name) -> IngestionResult.
        """
        started = _utc_now()
        start_perf = time.perf_counter()

        config_errors = self.validate_config(source_descriptor, config)
        if config_errors:
            return ConnectorRunResult(
                connector_name=self.name, success=False, error=config_errors[0],
                started_at=started, completed_at=_utc_now(),
                duration_ms=self._elapsed(start_perf),
            )

        fetch_result = self.fetch(source_descriptor, http_client, cache, config)

        if not fetch_result.success:
            return ConnectorRunResult(
                connector_name=self.name, success=False,
                fetch_result=fetch_result, error=fetch_result.error,
                started_at=started, completed_at=_utc_now(),
                duration_ms=self._elapsed(start_perf),
            )

        change = detect_change(source_descriptor["url"], fetch_result.body, cache)

        cache.set(source_descriptor["url"], CacheEntry(
            url=source_descriptor["url"],
            body=fetch_result.body,
            content_hash=compute_content_hash(fetch_result.body),
            etag=fetch_result.etag,
            last_modified=fetch_result.last_modified,
            fetched_at=fetch_result.fetched_at,
            content_type=fetch_result.content_type,
        ))

        if change.status in ("UNCHANGED", "DUPLICATE"):
            return ConnectorRunResult(
                connector_name=self.name, success=True,
                fetch_result=fetch_result, change_detection=change,
                items_parsed=0, ingestion_results=[],
                started_at=started, completed_at=_utc_now(),
                duration_ms=self._elapsed(start_perf),
            )

        try:
            parsed_items = self.parse(fetch_result, source_descriptor)
        except Exception as exc:
            error_type = getattr(exc, "error_type", "INVALID_CONTENT")
            return ConnectorRunResult(
                connector_name=self.name, success=False,
                fetch_result=fetch_result, change_detection=change,
                error=ConnectorError(
                    error_type=error_type, message=str(exc), recoverable=False,
                ),
                started_at=started, completed_at=_utc_now(),
                duration_ms=self._elapsed(start_perf),
            )

        ingestion_results = []
        for parsed_item in parsed_items:
            normalized = self.normalize(parsed_item, source_descriptor)
            payload, adapter_name = self.build_ingestion_payload(normalized, source_descriptor)
            ingestion_results.append(ingest_fn(payload, adapter_name))

        return ConnectorRunResult(
            connector_name=self.name, success=True,
            fetch_result=fetch_result, change_detection=change,
            items_parsed=len(parsed_items), ingestion_results=ingestion_results,
            started_at=started, completed_at=_utc_now(),
            duration_ms=self._elapsed(start_perf),
        )

    @staticmethod
    def _elapsed(start_perf):
        return round((time.perf_counter() - start_perf) * 1000, 3)
