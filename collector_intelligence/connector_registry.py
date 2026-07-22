"""
Atlas v21 - Module 6: connector registry / manager.
"""

from collector_intelligence.connector_cache import MemoryCache
from collector_intelligence.connector_models import (
    ConnectorBatchResult,
    ConnectorHealth,
    ScheduleState,
)
from collector_intelligence.connector_scheduler import record_run_outcome
from collector_intelligence.http_client import HTTPClient


class UnknownConnectorError(Exception):
    pass


class ConnectorManager:
    def __init__(self, http_client=None, cache=None):
        self._connectors = {}
        self._schedules = {}
        self._health = {}
        self.http_client = http_client or HTTPClient()
        self.cache = cache or MemoryCache()

    def register(self, connector, schedule=None):
        self._connectors[connector.name] = connector
        self._schedules[connector.name] = schedule or ScheduleState()

    def unregister(self, name):
        self._connectors.pop(name, None)
        self._schedules.pop(name, None)
        self._health.pop(name, None)

    def get(self, name):
        connector = self._connectors.get(name)
        if connector is None:
            raise UnknownConnectorError(f"No connector registered under {name!r}.")
        return connector

    def has(self, name):
        return name in self._connectors

    def list_connectors(self):
        return list(self._connectors.values())

    def list_names(self):
        return sorted(self._connectors)

    def get_schedule(self, name):
        return self._schedules.get(name)

    def get_health(self, name):
        return self._health.get(name)

    def run_connector(self, name, source_descriptor, config, ingest_fn):
        connector = self.get(name)
        effective_config = config.for_connector(name)

        result = connector.run(
            source_descriptor, self.http_client, self.cache, effective_config, ingest_fn,
        )

        schedule = self._schedules.get(name, ScheduleState())
        self._schedules[name] = record_run_outcome(schedule, result.success)

        self._health[name] = ConnectorHealth(
            connector_name=name,
            healthy=result.success,
            last_success_at=result.completed_at if result.success else (
                self._health[name].last_success_at if name in self._health else None
            ),
            consecutive_failures=(
                0 if result.success
                else self._health.get(name, ConnectorHealth(name, True)).consecutive_failures + 1
            ),
            last_error=result.error.message if result.error else None,
        )

        return result

    def run_all(self, source_descriptors_by_connector, config, ingest_fn):
        """
        `source_descriptors_by_connector`: {connector_name: [descriptor, ...]}.
        One connector/source failing never aborts the rest.
        """
        results = []

        for name, descriptors in source_descriptors_by_connector.items():
            for descriptor in descriptors:
                try:
                    results.append(self.run_connector(name, descriptor, config, ingest_fn))
                except UnknownConnectorError:
                    raise
                except Exception as exc:
                    from collector_intelligence.connector_models import (
                        ConnectorError, ConnectorRunResult,
                    )
                    results.append(ConnectorRunResult(
                        connector_name=name, success=False,
                        error=ConnectorError(
                            error_type="PERMANENT_FAILURE",
                            message=f"Unhandled error running {name}: {exc}",
                            recoverable=False,
                        ),
                    ))

        success_count = sum(1 for r in results if r.success)

        return ConnectorBatchResult(
            results=results,
            success_count=success_count,
            failure_count=len(results) - success_count,
            total_count=len(results),
        )
