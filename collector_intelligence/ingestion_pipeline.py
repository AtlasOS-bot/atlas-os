"""
Atlas v21 - Module 5: public ingestion API.

    source payload
        -> ingest_source() / ingest_batch()   (this module + adapters)
        -> RawSourceInput
        -> Module 2 detect_signals()
        -> Module 4 finalize_collector_opportunities()

process_ingested_sources() is the only function that touches Module 2
or Module 4 - it never duplicates their logic, only calls them.
"""

from collector_intelligence.adapter_registry import (
    UnknownAdapterError,
    get_default_registry,
)
from collector_intelligence.finalization import finalize_collector_opportunities
from collector_intelligence.ingestion_config import IngestionConfig
from collector_intelligence.ingestion_fingerprinting import content_similarity
from collector_intelligence.ingestion_models import (
    IngestionBatchResult,
    IngestionContext,
    IngestionResult,
    PayloadValidationError,
    new_id,
)


def _resolve_adapter(payload, adapter, context, config, registry):
    """
    Returns (adapter_instance_or_None, detection_failure_result_or_None).
    """
    if adapter is not None and not isinstance(adapter, str):
        return adapter, None  # already an adapter instance

    if isinstance(adapter, str):
        try:
            return registry.get(adapter), None
        except UnknownAdapterError as exc:
            return None, _unknown_adapter_result(adapter, str(exc))

    if not config.allow_automatic_detection:
        return None, _no_adapter_result(
            "No adapter was specified and automatic detection is disabled "
            "by configuration.",
        )

    detection = registry.detect(payload, config)

    if detection.adapter_name is None:
        if detection.ambiguous:
            return None, _ambiguous_result(detection)
        return None, _no_adapter_result(
            "; ".join(detection.reasons) or "No adapter could handle this payload.",
        )

    return registry.get(detection.adapter_name), None


def _no_adapter_result(message):
    return IngestionResult(
        success=False,
        validation_errors=[PayloadValidationError(
            field_name="adapter", error_code="NO_ADAPTER_MATCHED",
            message=message, severity="ERROR", recoverable=False,
        )],
        requires_manual_review=True,
        manual_review_reasons=[message],
    )


def _unknown_adapter_result(name, message):
    return IngestionResult(
        success=False,
        validation_errors=[PayloadValidationError(
            field_name="adapter", error_code="UNKNOWN_ADAPTER",
            message=message, severity="ERROR", recoverable=False,
        )],
        requires_manual_review=True,
        manual_review_reasons=[f"Unknown adapter {name!r} requested explicitly."],
    )


def _ambiguous_result(detection):
    message = (
        f"Adapter detection was ambiguous between {detection.alternatives} "
        f"(top confidence {detection.confidence:.2f}); an explicit adapter "
        f"must be supplied."
    )
    return IngestionResult(
        success=False,
        adapter_name=None,
        validation_warnings=[PayloadValidationError(
            field_name="adapter", error_code="AMBIGUOUS_ADAPTER_DETECTION",
            message=message, severity="WARNING", recoverable=True,
        )],
        requires_manual_review=True,
        manual_review_reasons=[message],
    )


def ingest_source(payload, adapter=None, context=None, config=None, registry=None):
    """
    Ingests one payload into an IngestionResult. `adapter` may be an
    adapter instance, a registered adapter name, or None (automatic
    detection, if config allows it).
    """
    context = context or IngestionContext()
    config = config or IngestionConfig()
    registry = registry or get_default_registry()

    resolved_adapter, failure = _resolve_adapter(payload, adapter, context, config, registry)

    if failure is not None:
        return failure

    return resolved_adapter.ingest(payload, context, config)


def _classify_duplicates(results, config):
    """
    Mutates nothing - returns a new list where duplicate successful
    results are flagged is_duplicate/duplicate_of, based on exact
    fingerprint matches within this batch.
    """
    if config.duplicate_policy == "allow":
        return results

    seen_combined = {}
    classified = []

    for result in results:
        if not result.success or not result.payload_fingerprint:
            classified.append(result)
            continue

        existing = seen_combined.get(result.payload_fingerprint)

        if existing is not None:
            result.is_duplicate = True
            result.duplicate_of = existing
        else:
            seen_combined[result.payload_fingerprint] = (
                result.adapter_name or "unknown"
            ) + ":" + result.payload_fingerprint

        classified.append(result)

    return classified


def ingest_batch(payloads, adapter=None, context=None, config=None, registry=None):
    """
    Ingests many payloads. Mixed source types are fine (adapter may be
    None to auto-detect per payload). One payload's failure never
    aborts the batch - every payload gets its own IngestionResult.
    """
    context = context or IngestionContext()
    config = config or IngestionConfig()
    registry = registry or get_default_registry()

    batch_id = context.batch_id or new_id("batch")

    results = []

    for payload in payloads:
        try:
            result = ingest_source(
                payload, adapter=adapter, context=context, config=config,
                registry=registry,
            )
        except Exception as exc:
            if not config.batch_partial_success:
                raise
            result = IngestionResult(
                success=False,
                validation_errors=[PayloadValidationError(
                    field_name="payload", error_code="UNEXPECTED_ERROR",
                    message=f"Unhandled error during ingestion: {exc}",
                    severity="ERROR", recoverable=False,
                )],
                requires_manual_review=True,
                manual_review_reasons=[f"Unhandled error: {exc}"],
            )

        results.append(result)

    results = _classify_duplicates(results, config)

    successful = [r for r in results if r.success and not r.is_duplicate]
    duplicates = [r for r in results if r.success and r.is_duplicate]
    failed = [r for r in results if not r.success]

    if config.duplicate_policy == "flag":
        # "flag" keeps duplicates in successful_results too (still
        # ingestible), just marked - only "skip" removes them.
        successful = [r for r in results if r.success]
        duplicates = [r for r in results if r.success and r.is_duplicate]

    warnings = []
    if duplicates:
        warnings.append(
            f"{len(duplicates)} payload(s) were exact duplicates of another "
            f"payload in this batch."
        )

    return IngestionBatchResult(
        results=results,
        successful_results=successful,
        failed_results=failed,
        duplicate_results=duplicates,
        total_count=len(results),
        success_count=len(successful),
        failure_count=len(failed),
        duplicate_count=len(duplicates),
        warnings=warnings,
        batch_id=batch_id,
    )


def process_ingested_sources(
    ingestion_result_or_batch,
    existing_opportunities=None,
    scoring_context=None,
    scoring_config=None,
    finalization_config=None,
):
    """
    Sends every successfully-ingested (and non-duplicate) RawSourceInput
    into Module 2 detection + Module 4 finalization. Failed and
    duplicate ingestion records never reach this stage. Returns
    {"ingestion": <input>, "finalization": <FinalizationBatchResult|None>}.
    """
    if isinstance(ingestion_result_or_batch, IngestionBatchResult):
        usable_results = ingestion_result_or_batch.successful_results
    else:
        usable_results = (
            [ingestion_result_or_batch] if ingestion_result_or_batch.success else []
        )

    dry_run = any(r.dry_run for r in usable_results)

    sources = [r.raw_source for r in usable_results if r.raw_source is not None]

    if not sources or dry_run:
        return {"ingestion": ingestion_result_or_batch, "finalization": None}

    finalization = finalize_collector_opportunities(
        sources,
        existing_opportunities=existing_opportunities,
        context=scoring_context,
        config=scoring_config,
        finalization_config=finalization_config,
    )

    return {"ingestion": ingestion_result_or_batch, "finalization": finalization}


__all__ = [
    "content_similarity",
    "ingest_batch",
    "ingest_source",
    "process_ingested_sources",
]
