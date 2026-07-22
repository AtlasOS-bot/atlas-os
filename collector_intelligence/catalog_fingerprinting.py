"""
Atlas v21 - Module 7: deterministic fingerprinting.

Every fingerprint is computed from a canonical JSON dump (sorted
keys, no whitespace) - equivalent structures with different input key
ordering always produce identical fingerprints.
"""

import hashlib
import json

from collector_intelligence.catalog_models import CatalogSnapshot


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value, algorithm="sha256"):
    digest = hashlib.new(algorithm)
    digest.update(_canonical_json(value).encode("utf-8"))
    return digest.hexdigest()


def fingerprint_catalog(catalog, algorithm="sha256"):
    # generated_at is an incidental load timestamp, not catalog
    # content - two structurally identical catalogs loaded at
    # different moments (or with reordered input) must fingerprint
    # identically.
    payload = catalog.to_dict()
    payload.pop("generated_at", None)
    return _hash(payload, algorithm)


def fingerprint_scout(scout, algorithm="sha256"):
    return _hash(scout.to_dict(), algorithm)


def fingerprint_source(source, algorithm="sha256"):
    return _hash(source.to_dict(), algorithm)


def fingerprint_execution_plan(plan, algorithm="sha256"):
    payload = {
        "items": [i.to_dict() for i in plan.items],
    }
    return _hash(payload, algorithm)


def snapshot_catalog(catalog, config=None):
    algorithm = config.fingerprint_algorithm if config else "sha256"
    payload = catalog.to_dict()

    return CatalogSnapshot(
        fingerprint=fingerprint_catalog(catalog, algorithm),
        catalog_version=catalog.catalog_version,
        source_count=len(catalog.sources),
        scout_count=len(catalog.scouts),
        brand_count=len(catalog.brands),
        normalized_payload=payload,
    )
