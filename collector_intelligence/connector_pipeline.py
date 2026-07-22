"""
Atlas v21 - Module 6: public connector pipeline API.

    Connector -> Module 5 ingestion -> Module 2 detection -> Module 4 finalization

Every stage reuses the existing module APIs directly - this file never
reimplements ingestion, detection, or finalization logic.
"""

from collector_intelligence.connector_cache import MemoryCache
from collector_intelligence.connector_config import ConnectorConfig
from collector_intelligence.connector_models import ConnectorBatchResult
from collector_intelligence.http_client import HTTPClient


def _default_ingest_fn(payload, adapter_name):
    from collector_intelligence.ingestion_pipeline import ingest_source
    return ingest_source(payload, adapter=adapter_name)


def fetch_source(url, config=None, http_client=None):
    """Fetches one URL and returns a FetchResult - no parsing, no
    ingestion, just the HTTP layer."""
    http_client = http_client or HTTPClient()
    config = config or ConnectorConfig()
    return http_client.get(url, config)


def fetch_batch(urls, config=None, http_client=None):
    """Fetches many URLs; one failure never aborts the rest."""
    http_client = http_client or HTTPClient()
    config = config or ConnectorConfig()
    return [http_client.get(url, config) for url in urls]


def run_connector(
    connector, source_descriptor, http_client=None, cache=None, config=None,
    ingest_fn=None,
):
    """Runs one connector against one source descriptor, all the way
    through Module 5 ingestion (fetch -> change detection -> parse ->
    normalize -> ingest)."""
    http_client = http_client or HTTPClient()
    cache = cache or MemoryCache()
    config = config or ConnectorConfig()
    ingest_fn = ingest_fn or _default_ingest_fn

    return connector.run(
        source_descriptor, http_client, cache, config.for_connector(connector.name),
        ingest_fn,
    )


def run_connector_batch(
    connector, source_descriptors, http_client=None, cache=None, config=None,
    ingest_fn=None,
):
    http_client = http_client or HTTPClient()
    cache = cache or MemoryCache()
    config = config or ConnectorConfig()
    ingest_fn = ingest_fn or _default_ingest_fn

    results = [
        run_connector(
            connector, descriptor, http_client=http_client, cache=cache,
            config=config, ingest_fn=ingest_fn,
        )
        for descriptor in source_descriptors
    ]

    success_count = sum(1 for r in results if r.success)

    return ConnectorBatchResult(
        results=results, success_count=success_count,
        failure_count=len(results) - success_count, total_count=len(results),
    )


def process_connector_run_results(
    run_results,
    existing_opportunities=None,
    scoring_context=None,
    scoring_config=None,
    finalization_config=None,
):
    """
    Collects every successfully-ingested RawSourceInput out of a list
    of ConnectorRunResult (or a ConnectorBatchResult) and sends it
    through Module 4's finalize_collector_opportunities() - the last
    leg of Connector -> Module 5 -> Module 2 -> Module 4. Returns None
    if there is nothing usable to finalize.
    """
    from collector_intelligence.finalization import finalize_collector_opportunities

    if isinstance(run_results, ConnectorBatchResult):
        run_results = run_results.results

    sources = []

    for run_result in run_results:
        if not run_result.success:
            continue
        for ingestion_result in run_result.ingestion_results:
            if (
                ingestion_result.success
                and not ingestion_result.is_duplicate
                and ingestion_result.raw_source is not None
            ):
                sources.append(ingestion_result.raw_source)

    if not sources:
        return None

    return finalize_collector_opportunities(
        sources,
        existing_opportunities=existing_opportunities,
        context=scoring_context,
        config=scoring_config,
        finalization_config=finalization_config,
    )


__all__ = [
    "fetch_source",
    "fetch_batch",
    "run_connector",
    "run_connector_batch",
    "process_connector_run_results",
]
