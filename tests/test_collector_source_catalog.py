"""
Atlas v21 - Module 7: Scout Definitions and Source Catalog.

No live network access anywhere in this file - every source URL in
every fixture uses the example.test reserved domain (RFC 2606).
"""

import copy
import json

import pytest

from collector_intelligence.catalog_config import CatalogConfig
from collector_intelligence.catalog_diff import diff_catalogs
from collector_intelligence.catalog_fingerprinting import (
    fingerprint_catalog,
    fingerprint_execution_plan,
    fingerprint_scout,
    fingerprint_source,
    snapshot_catalog,
)
from collector_intelligence.catalog_health import evaluate_source_health
from collector_intelligence.catalog_loading import (
    CatalogLoadError,
    UnsafePathError,
    load_catalog,
    yaml_available,
)
from collector_intelligence.catalog_models import SourceCatalog
from collector_intelligence.catalog_normalization import normalize_id
from collector_intelligence.catalog_planning import build_connector_plan, is_source_due
from collector_intelligence.catalog_queries import (
    UnknownScoutError,
    UnknownSourceError,
    get_scout,
    get_source,
    list_scouts,
    list_sources,
)
from collector_intelligence.catalog_validation import validate_catalog
from collector_intelligence.connector_models import ConnectorHealth
from collector_intelligence.example_catalog import build_example_catalog_data, load_example_catalog


def minimal_catalog_data(**overrides):
    data = {
        "catalog_version": "1.0.0",
        "categories": [{"category_id": "tcg", "name": "TCG"}],
        "brands": [{"brand_id": "brandx", "name": "Brand X", "categories": ["tcg"]}],
        "scouts": [{
            "scout_id": "scout1", "name": "Scout 1", "categories": ["tcg"],
            "brands": ["brandx"], "source_ids": ["source1"],
        }],
        "sources": [{
            "source_id": "source1", "name": "Source 1", "source_type": "rss_feed",
            "authority_level": "official_primary", "connector_type": "rss_connector",
            "url": "https://feed.example.test/rss.xml", "brand_id": "brandx",
            "scout_ids": ["scout1"], "lifecycle_state": "active",
            "schedule": {"mode": "hourly"},
        }],
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------
# Loading
# ---------------------------------------------------------------

class TestCatalogLoading:
    def test_load_dictionary_catalog(self):
        catalog = load_catalog(minimal_catalog_data())
        assert isinstance(catalog, SourceCatalog)
        assert "source1" in catalog.sources

    def test_load_json_text(self):
        text = json.dumps(minimal_catalog_data())
        catalog = load_catalog(text)
        assert "source1" in catalog.sources

    def test_load_yaml_when_supported(self):
        if not yaml_available():
            pytest.skip("PyYAML not installed")
        text = "scouts: []\nbrands: []\nsources: []\ncategories: []\n"
        catalog = load_catalog(text)
        assert catalog.sources == {}

    def test_graceful_yaml_unavailable_behavior(self):
        if yaml_available():
            pytest.skip("PyYAML is installed - can't exercise the unavailable path")
        with pytest.raises(CatalogLoadError, match="PyYAML is not installed"):
            load_catalog("scouts: []\nbrands: []\nsources: []\ncategories: []\n")

    def test_invalid_file_type_rejected(self, tmp_path):
        bad_file = tmp_path / "catalog.txt"
        bad_file.write_text("not a real catalog")
        with pytest.raises(CatalogLoadError, match="Unsupported catalog file type"):
            load_catalog(str(bad_file))

    def test_unsafe_path_rejected(self):
        with pytest.raises(UnsafePathError):
            load_catalog("/nonexistent/path/catalog.json")

    def test_oversized_catalog_rejected(self):
        config = CatalogConfig(maximum_catalog_size_bytes=10)
        with pytest.raises(CatalogLoadError, match="exceeds"):
            load_catalog(json.dumps(minimal_catalog_data()), config=config)

    def test_excessive_nesting_rejected(self):
        data = minimal_catalog_data()
        nested = {}
        cursor = nested
        for _ in range(30):
            cursor["child"] = {}
            cursor = cursor["child"]
        data["sources"][0]["metadata"] = nested
        config = CatalogConfig(maximum_metadata_depth=5)
        result = validate_catalog(data, config)
        assert not result.valid
        assert any(e.error_code == "CATALOG_TOO_DEEP" for e in result.errors)


# ---------------------------------------------------------------
# Uniqueness
# ---------------------------------------------------------------

class TestUniquenessValidation:
    def test_duplicate_scout_id(self):
        data = minimal_catalog_data()
        data["scouts"].append(dict(data["scouts"][0]))
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "DUPLICATE_SCOUT_ID" for e in result.errors)

    def test_duplicate_source_id(self):
        data = minimal_catalog_data()
        data["sources"].append(dict(data["sources"][0]))
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "DUPLICATE_SOURCE_ID" for e in result.errors)

    def test_duplicate_brand_id(self):
        data = minimal_catalog_data()
        data["brands"].append(dict(data["brands"][0]))
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "DUPLICATE_BRAND_ID" for e in result.errors)

    def test_duplicate_category_id(self):
        data = minimal_catalog_data()
        data["categories"].append(dict(data["categories"][0]))
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "DUPLICATE_CATEGORY_ID" for e in result.errors)


# ---------------------------------------------------------------
# References
# ---------------------------------------------------------------

class TestReferenceValidation:
    def test_missing_scout_reference(self):
        data = minimal_catalog_data()
        data["sources"][0]["scout_ids"] = ["nonexistent_scout"]
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "MISSING_SCOUT_REFERENCE" for e in result.errors)

    def test_missing_brand_reference(self):
        data = minimal_catalog_data()
        data["sources"][0]["brand_id"] = "nonexistent_brand"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "MISSING_BRAND_REFERENCE" for e in result.errors)

    def test_missing_category_reference(self):
        data = minimal_catalog_data()
        data["sources"][0]["category_ids"] = ["nonexistent_category"]
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "MISSING_CATEGORY_REFERENCE" for e in result.errors)

    def test_category_cycle_detected(self):
        data = minimal_catalog_data()
        data["categories"] = [
            {"category_id": "a", "name": "A", "parent_category_id": "b"},
            {"category_id": "b", "name": "B", "parent_category_id": "a"},
        ]
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "CATEGORY_CYCLE" for e in result.errors)


# ---------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------

class TestOwnershipValidation:
    def test_enabled_scout_with_no_source_warns(self):
        data = minimal_catalog_data()
        data["scouts"][0]["source_ids"] = []
        data["sources"][0]["scout_ids"] = []
        result = validate_catalog(data)
        assert result.valid
        assert any(w.error_code == "SCOUT_HAS_NO_RUNNABLE_SOURCE" for w in result.warnings)

    def test_enabled_source_with_no_scout_warns(self):
        data = minimal_catalog_data()
        data["scouts"][0]["source_ids"] = []
        data["sources"][0]["scout_ids"] = []
        result = validate_catalog(data)
        assert any(w.error_code == "SOURCE_HAS_NO_SCOUT" for w in result.warnings)


# ---------------------------------------------------------------
# Connector validation
# ---------------------------------------------------------------

class TestConnectorValidation:
    def test_unknown_connector_rejected(self):
        data = minimal_catalog_data()
        data["sources"][0]["connector_type"] = "not_a_real_connector"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "UNKNOWN_CONNECTOR" for e in result.errors)

    def test_connector_source_type_incompatibility(self):
        data = minimal_catalog_data()
        data["sources"][0]["source_type"] = "event_listing"
        data["sources"][0]["connector_type"] = "rss_connector"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "CONNECTOR_SOURCE_TYPE_MISMATCH" for e in result.errors)

    def test_missing_url_rejected(self):
        data = minimal_catalog_data()
        data["sources"][0]["url"] = None
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "MISSING_URL" for e in result.errors)

    def test_unsafe_url_scheme_rejected(self):
        data = minimal_catalog_data()
        data["sources"][0]["url"] = "javascript:alert(1)"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "INVALID_URL" for e in result.errors)

    def test_manual_report_needs_no_connector(self):
        data = minimal_catalog_data()
        data["sources"][0]["source_type"] = "manual_report"
        data["sources"][0]["connector_type"] = None
        data["sources"][0]["url"] = None
        result = validate_catalog(data)
        assert result.valid


# ---------------------------------------------------------------
# Field-level validation (schedule/priority/authority/lifecycle/etc.)
# ---------------------------------------------------------------

class TestFieldValidation:
    def test_invalid_schedule_mode(self):
        data = minimal_catalog_data()
        data["sources"][0]["schedule"] = {"mode": "biweekly"}
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "INVALID_SCHEDULE_MODE" for e in result.errors)

    def test_invalid_priority(self):
        data = minimal_catalog_data()
        data["scouts"][0]["priority"] = "urgent"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "INVALID_PRIORITY" for e in result.errors)

    def test_invalid_authority(self):
        data = minimal_catalog_data()
        data["sources"][0]["authority_level"] = "trust_me_bro"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "INVALID_AUTHORITY_LEVEL" for e in result.errors)

    def test_invalid_lifecycle(self):
        data = minimal_catalog_data()
        data["sources"][0]["lifecycle_state"] = "zombie"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "INVALID_LIFECYCLE_STATE" for e in result.errors)

    def test_invalid_expected_evidence_type(self):
        data = minimal_catalog_data()
        data["sources"][0]["expected_evidence"] = "not-a-mapping"
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "INVALID_EXPECTED_EVIDENCE" for e in result.errors)

    def test_invalid_health_policy_negative_threshold(self):
        data = minimal_catalog_data()
        data["sources"][0]["health_policy"] = {"max_consecutive_failures": -1}
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "NEGATIVE_HEALTH_THRESHOLD" for e in result.errors)


# ---------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------

class TestSecretDetection:
    def test_embedded_api_key_rejected(self):
        data = minimal_catalog_data()
        data["sources"][0]["connector_config"] = {"api_key": "sk-live-abc123"}
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "EMBEDDED_SECRET" for e in result.errors)

    def test_embedded_bearer_token_rejected(self):
        data = minimal_catalog_data()
        data["sources"][0]["metadata"] = {"bearer_token": "eyJhbGciOi..."}
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "EMBEDDED_SECRET" for e in result.errors)

    def test_symbolic_credential_reference_allowed(self):
        data = minimal_catalog_data()
        data["sources"][0]["connector_config"] = {"credential_ref": "TARGET_API_TOKEN"}
        result = validate_catalog(data)
        assert result.valid


# ---------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------

class TestNormalization:
    def test_metadata_json_compatibility_enforced(self):
        data = minimal_catalog_data()
        data["sources"][0]["metadata"] = {"bad": {1, 2, 3}}
        result = validate_catalog(data)
        assert not result.valid
        assert any(e.error_code == "METADATA_NOT_JSON_COMPATIBLE" for e in result.errors)

    def test_id_normalization(self):
        data = minimal_catalog_data()
        data["sources"][0]["source_id"] = "  Source One!! "
        data["scouts"][0]["source_ids"] = ["  Source One!! "]
        catalog = load_catalog(data)
        assert "source_one" in catalog.sources

    def test_url_canonicalization(self):
        data = minimal_catalog_data()
        data["sources"][0]["url"] = "HTTPS://Feed.Example.TEST/rss.xml#fragment"
        catalog = load_catalog(data)
        source = list(catalog.sources.values())[0]
        assert source.url == "https://feed.example.test/rss.xml"

    def test_alias_normalization_dedupes(self):
        data = minimal_catalog_data()
        data["brands"][0]["aliases"] = ["  Brand X TCG  ", "Brand X TCG", "Other Name"]
        catalog = load_catalog(data)
        assert catalog.brands["brandx"].aliases == ["Brand X TCG", "Other Name"]

    def test_tag_normalization(self):
        data = minimal_catalog_data()
        data["sources"][0]["tags"] = ["High Priority!", "high-priority", "  "]
        catalog = load_catalog(data)
        source = list(catalog.sources.values())[0]
        assert source.tags == ["high_priority"]

    def test_region_normalization(self):
        data = minimal_catalog_data()
        data["sources"][0]["region"] = "  us  "
        catalog = load_catalog(data)
        assert list(catalog.sources.values())[0].region == "US"

    def test_language_normalization(self):
        data = minimal_catalog_data()
        data["sources"][0]["language"] = "  EN  "
        catalog = load_catalog(data)
        assert list(catalog.sources.values())[0].language == "en"


# ---------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------

class TestInheritance:
    def test_schedule_inheritance_from_scout(self):
        catalog = load_example_catalog()
        source = catalog.sources["anime_expo_event_page"]
        scout = catalog.scouts["collector_events"]
        source.schedule.mode = None  # simulate no source-level override
        from collector_intelligence.catalog_planning import resolve_schedule
        resolved = resolve_schedule(source, [scout], catalog)
        assert resolved.mode == "daily"

    def test_source_schedule_overrides_scout_default(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]  # hourly
        scout = catalog.scouts["pokemon"]  # also hourly by default
        assert source.schedule.mode == "hourly"

    def test_connector_config_inheritance(self):
        catalog = load_example_catalog()
        source = catalog.sources["marketplace_sold_export"]
        from collector_intelligence.catalog_planning import resolve_connector_config
        merged = resolve_connector_config(source, [], catalog)
        assert merged["adapter_target"] == "marketplace_listing"

    def test_source_override_precedence_over_scout_default(self):
        from collector_intelligence.catalog_planning import resolve_connector_config
        data = minimal_catalog_data()
        data["scouts"][0]["default_connector_config"] = {"timeout_seconds": 5, "shared": "scout"}
        data["sources"][0]["connector_config"] = {"timeout_seconds": 30}
        catalog = load_catalog(data)
        source = catalog.sources["source1"]
        scout = catalog.scouts["scout1"]
        merged = resolve_connector_config(source, [scout], catalog)
        assert merged["timeout_seconds"] == 30
        assert merged["shared"] == "scout"

    def test_inheritance_does_not_mutate_inputs(self):
        from collector_intelligence.catalog_planning import resolve_connector_config
        data = minimal_catalog_data()
        data["scouts"][0]["default_connector_config"] = {"a": 1}
        data["sources"][0]["connector_config"] = {"b": 2}
        catalog = load_catalog(data)
        source = catalog.sources["source1"]
        scout = catalog.scouts["scout1"]
        before_scout = dict(scout.default_connector_config)
        before_source = dict(source.connector_config)
        resolve_connector_config(source, [scout], catalog)
        assert scout.default_connector_config == before_scout
        assert source.connector_config == before_source


# ---------------------------------------------------------------
# Shared ownership / deduplication
# ---------------------------------------------------------------

class TestSharedOwnership:
    def test_shared_source_ownership_recorded_both_directions(self):
        catalog = load_example_catalog()
        source = catalog.sources["bandai_one_piece_announcements"]
        assert set(source.scout_ids) == {"one_piece_tcg", "broad_tcg"}
        assert "bandai_one_piece_announcements" in catalog.scouts["one_piece_tcg"].source_ids
        assert "bandai_one_piece_announcements" in catalog.scouts["broad_tcg"].source_ids

    def test_shared_source_deduplicated_in_plan(self):
        catalog = load_example_catalog()
        plan = build_connector_plan(catalog)
        source_ids = [item.source_id for item in plan.items]
        assert source_ids.count("bandai_one_piece_announcements") == 1
        assert source_ids.count("round1_promo_announcements") == 1

    def test_owning_scout_ids_preserved_in_plan_metadata(self):
        catalog = load_example_catalog()
        plan = build_connector_plan(catalog)
        item = next(i for i in plan.items if i.source_id == "bandai_one_piece_announcements")
        assert set(item.metadata["owning_scout_ids"]) == {"one_piece_tcg", "broad_tcg"}


# ---------------------------------------------------------------
# Lifecycle states
# ---------------------------------------------------------------

class TestLifecycleStates:
    def test_disabled_scout_excluded_from_queries(self):
        data = minimal_catalog_data()
        data["scouts"][0]["enabled"] = False
        catalog = load_catalog(data)
        assert list_scouts(catalog, {"enabled": True}) == []

    def test_disabled_source_excluded_from_plan(self):
        data = minimal_catalog_data()
        data["sources"][0]["enabled"] = False
        catalog = load_catalog(data)
        plan = build_connector_plan(catalog)
        assert plan.items == []
        assert plan.disabled_items[0]["reason"] == "source is disabled"

    def test_proposed_source_excluded_by_default(self):
        data = minimal_catalog_data()
        data["sources"][0]["lifecycle_state"] = "proposed"
        catalog = load_catalog(data)
        plan = build_connector_plan(catalog)
        assert plan.items == []
        assert "proposed" in plan.disabled_items[0]["reason"]

    def test_proposed_source_included_when_allowed(self):
        data = minimal_catalog_data()
        data["sources"][0]["lifecycle_state"] = "proposed"
        catalog = load_catalog(data)
        config = CatalogConfig(allow_proposed_sources_in_plan=True)
        plan = build_connector_plan(catalog, config=config)
        assert len(plan.items) == 1

    def test_active_source_included(self):
        catalog = load_example_catalog()
        plan = build_connector_plan(catalog)
        assert any(i.source_id == "pokemon_official_rss" for i in plan.items)

    def test_paused_source_excluded(self):
        data = minimal_catalog_data()
        data["sources"][0]["lifecycle_state"] = "paused"
        catalog = load_catalog(data)
        plan = build_connector_plan(catalog)
        assert plan.items == []
        assert plan.disabled_items[0]["reason"] == "source is paused"

    def test_deprecated_source_runs_with_warning(self):
        data = minimal_catalog_data()
        data["sources"][0]["lifecycle_state"] = "deprecated"
        catalog = load_catalog(data)
        plan = build_connector_plan(catalog)
        assert len(plan.items) == 1
        assert any("deprecated" in w for w in plan.warnings)

    def test_retired_source_never_runs(self):
        data = minimal_catalog_data()
        data["sources"][0]["lifecycle_state"] = "retired"
        catalog = load_catalog(data)
        plan = build_connector_plan(catalog)
        assert plan.items == []
        assert plan.disabled_items[0]["reason"] == "source is retired"

    def test_broken_source_excluded_and_marked_invalid(self):
        data = minimal_catalog_data()
        data["sources"][0]["lifecycle_state"] = "broken"
        catalog = load_catalog(data)
        plan = build_connector_plan(catalog)
        assert plan.items == []
        assert plan.invalid_items[0]["reason"] == "source is marked broken"


# ---------------------------------------------------------------
# Scheduling / due status
# ---------------------------------------------------------------

class TestScheduling:
    def test_manual_schedule_never_due(self):
        data = minimal_catalog_data()
        data["sources"][0]["schedule"] = {"mode": "manual"}
        catalog = load_catalog(data)
        due, reason = is_source_due(catalog, catalog.sources["source1"])
        assert due is False

    def test_hourly_schedule_is_due(self):
        data = minimal_catalog_data()
        data["sources"][0]["schedule"] = {"mode": "hourly"}
        catalog = load_catalog(data)
        due, _ = is_source_due(catalog, catalog.sources["source1"])
        assert due is True

    def test_daily_schedule_is_due(self):
        data = minimal_catalog_data()
        data["sources"][0]["schedule"] = {"mode": "daily"}
        catalog = load_catalog(data)
        due, _ = is_source_due(catalog, catalog.sources["source1"])
        assert due is True

    def test_cron_schedule_is_due(self):
        data = minimal_catalog_data()
        data["sources"][0]["schedule"] = {"mode": "cron", "cron_expression": "0 * * * *"}
        catalog = load_catalog(data)
        due, _ = is_source_due(catalog, catalog.sources["source1"])
        assert due is True

    def test_disabled_schedule_never_due(self):
        data = minimal_catalog_data()
        data["sources"][0]["schedule"] = {"mode": "disabled"}
        catalog = load_catalog(data)
        due, reason = is_source_due(catalog, catalog.sources["source1"])
        assert due is False
        assert "disabled" in reason

    def test_due_and_not_due_both_appear_in_plan_buckets(self):
        data = minimal_catalog_data()
        data["sources"].append({
            "source_id": "source2", "name": "Source 2", "source_type": "rss_feed",
            "authority_level": "official_primary", "connector_type": "rss_connector",
            "url": "https://feed2.example.test/rss.xml", "brand_id": "brandx",
            "scout_ids": ["scout1"], "lifecycle_state": "active",
            "schedule": {"mode": "manual"},
        })
        data["scouts"][0]["source_ids"].append("source2")
        catalog = load_catalog(data)
        plan = build_connector_plan(catalog)
        assert len(plan.due_items) == 1
        assert len(plan.skipped_items) == 1


# ---------------------------------------------------------------
# Plan ordering
# ---------------------------------------------------------------

class TestPlanOrdering:
    def test_priority_ordering(self):
        catalog = load_example_catalog()
        plan = build_connector_plan(catalog)
        priorities = [item.priority for item in plan.items]
        from collector_intelligence.catalog_models import PRIORITY_RANK
        ranks = [PRIORITY_RANK[p] for p in priorities]
        assert ranks == sorted(ranks)

    def test_authority_ordering_within_same_priority(self):
        catalog = load_example_catalog()
        plan = build_connector_plan(catalog)
        from collector_intelligence.catalog_models import AUTHORITY_RANK, PRIORITY_RANK
        high_priority_items = [i for i in plan.items if i.priority == "high"]
        authority_ranks = [AUTHORITY_RANK[i.authority_level] for i in high_priority_items]
        assert authority_ranks == sorted(authority_ranks)

    def test_plan_ordering_is_deterministic_across_runs(self):
        catalog = load_example_catalog()
        plan_a = build_connector_plan(catalog)
        plan_b = build_connector_plan(catalog)
        assert [i.source_id for i in plan_a.items] == [i.source_id for i in plan_b.items]


# ---------------------------------------------------------------
# Querying
# ---------------------------------------------------------------

class TestQuerying:
    def test_get_scout(self):
        catalog = load_example_catalog()
        scout = get_scout(catalog, "pokemon")
        assert scout.name == "Pokemon Scout"

    def test_get_scout_unknown_raises(self):
        catalog = load_example_catalog()
        with pytest.raises(UnknownScoutError):
            get_scout(catalog, "nonexistent")

    def test_get_source(self):
        catalog = load_example_catalog()
        source = get_source(catalog, "pokemon_official_rss")
        assert source.connector_type == "rss_connector"

    def test_get_source_unknown_raises(self):
        catalog = load_example_catalog()
        with pytest.raises(UnknownSourceError):
            get_source(catalog, "nonexistent")

    def test_query_by_scout(self):
        catalog = load_example_catalog()
        results = list_sources(catalog, {"scout": "one_piece_tcg"})
        assert {s.source_id for s in results} == {
            "bandai_one_piece_announcements", "round1_promo_announcements",
        }

    def test_query_by_brand(self):
        catalog = load_example_catalog()
        results = list_sources(catalog, {"brand": "round1"})
        assert {s.source_id for s in results} == {"round1_promo_announcements"}

    def test_query_by_category(self):
        catalog = load_example_catalog()
        results = list_sources(catalog, {"category": "events"})
        assert {s.source_id for s in results} == {"anime_expo_event_page"}

    def test_query_by_source_type(self):
        catalog = load_example_catalog()
        results = list_sources(catalog, {"source_type": "rss_feed"})
        assert {s.source_id for s in results} == {"pokemon_official_rss"}

    def test_query_by_connector(self):
        catalog = load_example_catalog()
        results = list_sources(catalog, {"connector": "event_connector"})
        assert {s.source_id for s in results} == {"anime_expo_event_page"}

    def test_query_by_priority(self):
        catalog = load_example_catalog()
        results = list_scouts(catalog, {"priority": "critical"})
        assert {s.scout_id for s in results} == {"pokemon", "one_piece_tcg"}

    def test_query_by_authority(self):
        catalog = load_example_catalog()
        results = list_sources(catalog, {"authority": "marketplace_confirmed_sale"})
        assert {s.source_id for s in results} == {"marketplace_sold_export"}

    def test_query_by_lifecycle(self):
        catalog = load_example_catalog()
        results = list_sources(catalog, {"lifecycle": "proposed"})
        assert {s.source_id for s in results} == {"best_buy_collectibles_page"}

    def test_query_by_tags(self):
        data = minimal_catalog_data()
        data["sources"][0]["tags"] = ["featured"]
        catalog = load_catalog(data)
        results = list_sources(catalog, {"tags": ["featured"]})
        assert len(results) == 1

    def test_query_by_region(self):
        data = minimal_catalog_data()
        data["sources"][0]["region"] = "US"
        catalog = load_catalog(data)
        results = list_sources(catalog, {"region": "US"})
        assert len(results) == 1

    def test_query_by_language(self):
        data = minimal_catalog_data()
        data["sources"][0]["language"] = "en"
        catalog = load_catalog(data)
        results = list_sources(catalog, {"language": "en"})
        assert len(results) == 1

    def test_query_returns_deterministic_order(self):
        catalog = load_example_catalog()
        results_a = list_sources(catalog)
        results_b = list_sources(catalog)
        assert [s.source_id for s in results_a] == [s.source_id for s in results_b]
        assert [s.source_id for s in results_a] == sorted(s.source_id for s in results_a)


# ---------------------------------------------------------------
# Health state
# ---------------------------------------------------------------

class TestHealthState:
    def test_health_status_healthy(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        health = ConnectorHealth(connector_name="rss_connector", healthy=True, last_success_at="2026-07-20T00:00:00+00:00")
        state = evaluate_source_health(source, health, now=__import__("datetime").datetime(2026, 7, 20, 1, tzinfo=__import__("datetime").timezone.utc))
        assert state.health_status == "healthy"

    def test_health_status_warning(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        health = ConnectorHealth(connector_name="rss_connector", healthy=False, consecutive_failures=1, last_success_at="2026-07-19T00:00:00+00:00")
        state = evaluate_source_health(source, health)
        assert state.health_status == "warning"
        assert state.recommended_catalog_action == "retry"

    def test_health_status_failing(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        health = ConnectorHealth(connector_name="rss_connector", healthy=False, consecutive_failures=20)
        state = evaluate_source_health(source, health)
        assert state.health_status == "failing"

    def test_health_status_stale(self):
        from datetime import datetime, timezone
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        source.health_policy.stale_after = 24.0
        health = ConnectorHealth(connector_name="rss_connector", healthy=True, last_success_at="2026-01-01T00:00:00+00:00")
        state = evaluate_source_health(source, health, now=datetime(2026, 7, 20, tzinfo=timezone.utc))
        assert state.health_status == "stale"

    def test_health_recommendation_pause(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        source.health_policy.disable_after_failures = 3
        source.health_policy.permanent_failure_action = "pause"
        health = ConnectorHealth(connector_name="rss_connector", healthy=False, consecutive_failures=5)
        state = evaluate_source_health(source, health)
        assert state.recommended_catalog_action == "pause"

    def test_health_recommendation_replace(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        source.health_policy.disable_after_failures = 3
        source.health_policy.permanent_failure_action = "replace"
        health = ConnectorHealth(connector_name="rss_connector", healthy=False, consecutive_failures=5)
        state = evaluate_source_health(source, health)
        assert state.recommended_catalog_action == "replace"

    def test_health_never_mutates_catalog(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        before = source.to_dict()
        health = ConnectorHealth(connector_name="rss_connector", healthy=False, consecutive_failures=20)
        evaluate_source_health(source, health)
        assert source.to_dict() == before


# ---------------------------------------------------------------
# Snapshot / fingerprinting
# ---------------------------------------------------------------

class TestFingerprinting:
    def test_catalog_snapshot(self):
        catalog = load_example_catalog()
        snapshot = snapshot_catalog(catalog)
        assert snapshot.source_count == 8
        assert snapshot.scout_count == 5
        assert snapshot.fingerprint

    def test_deterministic_catalog_fingerprint(self):
        catalog = load_example_catalog()
        assert fingerprint_catalog(catalog) == fingerprint_catalog(catalog)

    def test_key_order_independent_fingerprint(self):
        data_a = build_example_catalog_data()
        data_b = json.loads(json.dumps(data_a))
        data_b["sources"] = list(reversed(data_b["sources"]))
        data_b["scouts"] = list(reversed(data_b["scouts"]))
        catalog_a = load_catalog(data_a)
        catalog_b = load_catalog(data_b)
        assert fingerprint_catalog(catalog_a) == fingerprint_catalog(catalog_b)

    def test_scout_fingerprint(self):
        catalog = load_example_catalog()
        scout = catalog.scouts["pokemon"]
        assert fingerprint_scout(scout) == fingerprint_scout(scout)

    def test_source_fingerprint(self):
        catalog = load_example_catalog()
        source = catalog.sources["pokemon_official_rss"]
        other = catalog.sources["round1_promo_announcements"]
        assert fingerprint_source(source) != fingerprint_source(other)

    def test_execution_plan_fingerprint(self):
        catalog = load_example_catalog()
        plan_a = build_connector_plan(catalog)
        plan_b = build_connector_plan(catalog)
        assert fingerprint_execution_plan(plan_a) == fingerprint_execution_plan(plan_b)


# ---------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------

class TestCatalogDiff:
    def _catalog_with_change(self, mutator):
        data = copy.deepcopy(build_example_catalog_data())
        mutator(data)
        return load_catalog(data)

    @staticmethod
    def _remove_source(data, source_id):
        data["sources"] = [s for s in data["sources"] if s["source_id"] != source_id]
        for scout in data["scouts"]:
            scout["source_ids"] = [sid for sid in scout["source_ids"] if sid != source_id]

    def test_source_added(self):
        old = load_example_catalog()
        new = self._catalog_with_change(lambda d: d["sources"].append({
            "source_id": "new_source", "name": "New", "source_type": "rss_feed",
            "authority_level": "official_primary", "connector_type": "rss_connector",
            "url": "https://new.example.test/rss.xml", "lifecycle_state": "active",
            "schedule": {"mode": "daily"},
        }))
        diff = diff_catalogs(old, new)
        assert "new_source" in diff.added_sources

    def test_source_removed(self):
        old = load_example_catalog()
        new = self._catalog_with_change(lambda d: self._remove_source(d, "anime_expo_event_page"))
        diff = diff_catalogs(old, new)
        assert "anime_expo_event_page" in diff.removed_sources

    def test_source_url_changed(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "pokemon_official_rss":
                    s["url"] = "https://different.example.test/feed.xml"

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        entry = next(c for c in diff.changed_sources if c["source_id"] == "pokemon_official_rss")
        assert "url" in entry["changed_fields"]

    def test_source_enabled_state_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "pokemon_official_rss":
                    s["enabled"] = False

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert "pokemon_official_rss" in diff.disabled_sources

    def test_lifecycle_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "best_buy_collectibles_page":
                    s["lifecycle_state"] = "active"

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        entry = next(c for c in diff.changed_sources if c["source_id"] == "best_buy_collectibles_page")
        assert "lifecycle_state" in entry["changed_fields"]

    def test_schedule_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "pokemon_official_rss":
                    s["schedule"] = {"mode": "daily"}

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert any(c["source_id"] == "pokemon_official_rss" for c in diff.changed_schedules)

    def test_connector_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "target_collectibles_page":
                    s["connector_type"] = "html_connector"
                    s["source_type"] = "retailer_category_page"

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert any("connector changed" in b for b in diff.breaking_changes)

    def test_connector_config_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "marketplace_sold_export":
                    s["connector_config"] = {"adapter_target": "marketplace_listing", "items_path": ["data"]}

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert any(c["source_id"] == "marketplace_sold_export" for c in diff.changed_connector_configs)

    def test_authority_diff_breaking_when_downgraded(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "pokemon_official_rss":
                    s["authority_level"] = "community_unverified"

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert any("downgraded" in b for b in diff.breaking_changes)

    def test_scout_ownership_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "round1_promo_announcements":
                    s["scout_ids"] = ["one_piece_tcg"]  # dropped general_retail_drops
            for scout in d["scouts"]:
                if scout["scout_id"] == "general_retail_drops":
                    scout["source_ids"] = [
                        sid for sid in scout["source_ids"] if sid != "round1_promo_announcements"
                    ]

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert any(c.get("source_id") == "round1_promo_announcements" for c in diff.changed_scouts)

    def test_expected_evidence_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "marketplace_sold_export":
                    s["expected_evidence"]["supports_market_price"] = False

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        entry = next(c for c in diff.changed_sources if c["source_id"] == "marketplace_sold_export")
        assert "expected_evidence" in entry["changed_fields"]

    def test_health_policy_diff(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "pokemon_official_rss":
                    s["health_policy"] = {"stale_after": 12.0}

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        entry = next(c for c in diff.changed_sources if c["source_id"] == "pokemon_official_rss")
        assert "health_policy" in entry["changed_fields"]

    def test_breaking_source_id_reused_for_different_url(self):
        old = load_example_catalog()

        def mutate(d):
            for s in d["sources"]:
                if s["source_id"] == "pokemon_official_rss":
                    s["url"] = "https://totally-different.example.test/feed.xml"

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert any("canonical URL changed" in b for b in diff.breaking_changes)

    def test_breaking_active_source_removed(self):
        old = load_example_catalog()
        new = self._catalog_with_change(lambda d: self._remove_source(d, "pokemon_official_rss"))
        diff = diff_catalogs(old, new)
        assert any("was removed entirely" in b for b in diff.breaking_changes)

    def test_breaking_scout_loses_all_sources(self):
        old = load_example_catalog()

        def mutate(d):
            self._remove_source(d, "bandai_one_piece_announcements")
            self._remove_source(d, "round1_promo_announcements")

        new = self._catalog_with_change(mutate)
        diff = diff_catalogs(old, new)
        assert any("one_piece_tcg" in b and "zero runnable" in b for b in diff.breaking_changes)


# ---------------------------------------------------------------
# Round1 scenario
# ---------------------------------------------------------------

class TestRound1Scenario:
    def test_one_piece_scout_watches_bandai_and_round1(self):
        catalog = load_example_catalog()
        scout = catalog.scouts["one_piece_tcg"]
        assert "bandai_one_piece_announcements" in scout.source_ids
        assert "round1_promo_announcements" in scout.source_ids

    def test_broad_tcg_shares_bandai_source(self):
        catalog = load_example_catalog()
        assert "bandai_one_piece_announcements" in catalog.scouts["broad_tcg"].source_ids

    def test_general_retail_shares_round1_source(self):
        catalog = load_example_catalog()
        assert "round1_promo_announcements" in catalog.scouts["general_retail_drops"].source_ids

    def test_shared_sources_fetched_once_in_plan(self):
        catalog = load_example_catalog()
        plan = build_connector_plan(catalog)
        ids = [i.source_id for i in plan.items]
        assert ids.count("bandai_one_piece_announcements") == 1
        assert ids.count("round1_promo_announcements") == 1

    def test_official_and_retailer_authority_retained(self):
        catalog = load_example_catalog()
        assert catalog.sources["bandai_one_piece_announcements"].authority_level == "official_primary"
        assert catalog.sources["round1_promo_announcements"].authority_level == "authorized_retailer"

    def test_marketplace_export_labeled_confirmed_sale(self):
        catalog = load_example_catalog()
        source = catalog.sources["marketplace_sold_export"]
        assert source.authority_level == "marketplace_confirmed_sale"
        assert source.expected_evidence.price_kind == "sold"

    def test_marketplace_export_scoped_to_complete_set_not_one_pack(self):
        catalog = load_example_catalog()
        source = catalog.sources["marketplace_sold_export"]
        assert source.expected_evidence.expected_unit_scope == "complete_set"

    def test_no_one_pack_sold_source_exists_anywhere(self):
        catalog = load_example_catalog()
        for source in catalog.sources.values():
            assert source.expected_evidence.expected_unit_scope != "pack" or source.expected_evidence.price_kind != "sold"

    def test_module_7_performs_no_scoring(self):
        import collector_intelligence.catalog_models as m1
        import collector_intelligence.catalog_planning as m2
        import collector_intelligence.catalog_validation as m3
        for module in (m1, m2, m3):
            source = module.__file__
            with open(source) as f:
                content = f.read()
            assert "decision_engine" not in content
            assert "evaluate_opportunity" not in content
            assert "scoring_config" not in content


# ---------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------

class TestDeterminism:
    def test_repeated_loads_produce_identical_normalized_catalog(self):
        data = build_example_catalog_data()
        catalog_a = load_catalog(data)
        catalog_b = load_catalog(data)
        payload_a = catalog_a.to_dict()
        payload_b = catalog_b.to_dict()
        payload_a.pop("generated_at")
        payload_b.pop("generated_at")
        assert payload_a == payload_b

    def test_normalize_id_is_deterministic(self):
        assert normalize_id("  Pokemon TCG!! ") == normalize_id("Pokemon TCG!!")
