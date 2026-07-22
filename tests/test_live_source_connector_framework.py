"""
Atlas v21 - Module 6: Live Source Connector Framework.

Every test uses FakeTransport - no real network access anywhere in
this file, directly or indirectly.
"""

from datetime import datetime, timezone

import tests.connector_fixtures as fx
from collector_intelligence.change_detection import detect_change
from collector_intelligence.connector_cache import MemoryCache, compute_content_hash, is_stale
from collector_intelligence.connector_config import ConnectorConfig
from collector_intelligence.connector_models import ScheduleState
from collector_intelligence.connector_parsing import ParsingError, parse_json, parse_rss_or_atom, parse_xml
from collector_intelligence.connector_pipeline import (
    fetch_batch,
    fetch_source,
    process_connector_run_results,
    run_connector,
    run_connector_batch,
)
from collector_intelligence.connector_registry import ConnectorManager, UnknownConnectorError
from collector_intelligence.connector_scheduler import (
    compute_backoff_seconds,
    compute_next_cron_run,
    compute_next_run,
    record_run_outcome,
)
from collector_intelligence.connectors import (
    AnnouncementConnector,
    EventConnector,
    HTMLConnector,
    JSONConnector,
    RetailerPageConnector,
    RSSConnector,
    XMLConnector,
    build_default_manager,
)
from collector_intelligence.http_client import FakeTransport, HTTPClient, make_response
from collector_intelligence.ingestion_pipeline import ingest_source


def ingest_fn(payload, adapter_name):
    return ingest_source(payload, adapter=adapter_name)


def client_for(url_responses, sleep=True):
    transport = FakeTransport()
    for url, responses in url_responses.items():
        if not isinstance(responses, list):
            responses = [responses]
        for response in responses:
            transport.plan(url, response)
    return HTTPClient(transport=transport, sleep_fn=(lambda s: None) if sleep else None), transport


def html_response(body, content_type="text/html"):
    return make_response(200, body=body, headers={"Content-Type": content_type})


# ---------------------------------------------------------------
# RSSConnector
# ---------------------------------------------------------------

class TestRSSConnector:
    def test_rss_retrieval(self):
        client, _ = client_for({"https://example.com/feed.xml": html_response(
            fx.ROUND1_RSS_FEED_XML, "application/rss+xml",
        )})
        connector = RSSConnector()
        result = run_connector(
            connector, {"url": "https://example.com/feed.xml", "type": "rss"},
            http_client=client, config=ConnectorConfig(), ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.items_parsed == 1
        assert result.ingestion_results[0].success
        assert "One Piece" in result.ingestion_results[0].raw_source.title

    def test_atom_feed_retrieval(self):
        client, _ = client_for({"https://example.com/atom": html_response(
            fx.GENERIC_ATOM_FEED_XML, "application/atom+xml",
        )})
        connector = RSSConnector()
        result = run_connector(
            connector, {"url": "https://example.com/atom", "type": "atom"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.items_parsed == 1
        assert result.ingestion_results[0].raw_source.raw_metadata["guid"] == "atom-guid-1"

    def test_invalid_rss_produces_structured_error(self):
        client, _ = client_for({"https://example.com/bad.xml": html_response(fx.INVALID_RSS_XML)})
        connector = RSSConnector()
        result = run_connector(
            connector, {"url": "https://example.com/bad.xml", "type": "rss"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert not result.success
        assert result.error.error_type == "INVALID_RSS"

    def test_supports_checks_type(self):
        connector = RSSConnector()
        assert connector.supports({"type": "rss"})
        assert not connector.supports({"type": "html"})


# ---------------------------------------------------------------
# HTMLConnector
# ---------------------------------------------------------------

class TestHTMLConnector:
    def test_html_retrieval(self):
        client, _ = client_for({"https://example.com/page": html_response(
            "<html><head><title>Brand X</title></head><body><p>Brand X and Partner Co launched a collaboration.</p></body></html>",
        )})
        connector = HTMLConnector()
        result = run_connector(
            connector, {"url": "https://example.com/page", "type": "html"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.ingestion_results[0].raw_source.title == "Brand X"


# ---------------------------------------------------------------
# JSONConnector
# ---------------------------------------------------------------

class TestJSONConnector:
    def test_json_retrieval(self):
        client, _ = client_for({"https://example.com/feed.json": html_response(
            fx.GENERIC_JSON_FEED, "application/json",
        )})
        connector = JSONConnector()
        result = run_connector(
            connector,
            {
                "url": "https://example.com/feed.json", "type": "json",
                "adapter_target": "generic_article", "items_path": ["articles"],
            },
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.items_parsed == 1
        assert result.ingestion_results[0].raw_source.title == "Brand X News"

    def test_invalid_json_produces_structured_error(self):
        client, _ = client_for({"https://example.com/bad.json": html_response(
            fx.INVALID_JSON_TEXT, "application/json",
        )})
        connector = JSONConnector()
        result = run_connector(
            connector,
            {"url": "https://example.com/bad.json", "type": "json", "adapter_target": "generic_article"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert not result.success
        assert result.error.error_type == "INVALID_JSON"

    def test_missing_adapter_target_is_config_invalid(self):
        client, _ = client_for({"https://example.com/feed.json": html_response(fx.GENERIC_JSON_FEED)})
        connector = JSONConnector()
        result = run_connector(
            connector, {"url": "https://example.com/feed.json", "type": "json"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert not result.success
        assert result.error.error_type == "CONFIG_INVALID"


# ---------------------------------------------------------------
# XMLConnector
# ---------------------------------------------------------------

class TestXMLConnector:
    def test_xml_retrieval(self):
        client, _ = client_for({"https://example.com/feed.xml": html_response(
            fx.GENERIC_XML_FEED, "application/xml",
        )})
        connector = XMLConnector()
        result = run_connector(
            connector,
            {
                "url": "https://example.com/feed.xml", "type": "xml",
                "adapter_target": "retailer_product", "items_path": ["products", "product"],
            },
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.ingestion_results[0].raw_source.title == "Brand X Item"

    def test_invalid_xml_produces_structured_error(self):
        client, _ = client_for({"https://example.com/bad.xml": html_response(fx.INVALID_XML_TEXT)})
        connector = XMLConnector()
        result = run_connector(
            connector, {"url": "https://example.com/bad.xml", "type": "xml", "adapter_target": "generic_article"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert not result.success
        assert result.error.error_type == "INVALID_XML"


# ---------------------------------------------------------------
# AnnouncementConnector / RetailerPageConnector / EventConnector
# ---------------------------------------------------------------

class TestAnnouncementConnector:
    def test_announcement_parsing_defaults_official(self):
        client, _ = client_for({"https://round1.example.com/news": html_response(
            fx.ROUND1_OFFICIAL_ANNOUNCEMENT_HTML,
        )})
        connector = AnnouncementConnector()
        result = run_connector(
            connector, {"url": "https://round1.example.com/news", "type": "announcement"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.ingestion_results[0].raw_source.source_type == "OFFICIAL"


class TestRetailerPageConnector:
    def test_retailer_parsing_via_json_ld(self):
        client, _ = client_for({"https://round1.example.com/product": html_response(
            fx.ROUND1_RETAILER_PAGE_HTML,
        )})
        connector = RetailerPageConnector()
        result = run_connector(
            connector,
            {"url": "https://round1.example.com/product", "type": "retailer_page", "retailer": "Round1"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        raw_source = result.ingestion_results[0].raw_source
        assert "$200" in raw_source.body
        assert raw_source.retailer == "Round1"


class TestEventConnector:
    def test_event_parsing_via_json_ld(self):
        client, _ = client_for({"https://round1.example.com/event": html_response(
            fx.ROUND1_EVENT_PAGE_HTML,
        )})
        connector = EventConnector()
        result = run_connector(
            connector, {"url": "https://round1.example.com/event", "type": "event_page"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.ingestion_results[0].raw_source.source_type == "EVENT"
        assert "Round1 Downtown" in result.ingestion_results[0].raw_source.body


# ---------------------------------------------------------------
# Caching: hit, miss, ETag, Last-Modified
# ---------------------------------------------------------------

class TestCaching:
    def test_cache_miss_then_hit(self):
        cache = MemoryCache()
        assert cache.get("https://example.com/x") is None

        from collector_intelligence.connector_cache import CacheEntry
        entry = CacheEntry(
            url="https://example.com/x", body="hello",
            content_hash=compute_content_hash("hello"), fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        cache.set("https://example.com/x", entry)
        assert cache.get("https://example.com/x") is entry

    def test_etag_sent_on_second_fetch(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", make_response(
            200, body="v1", headers={"ETag": '"abc"', "Content-Type": "text/plain"},
        ))
        transport.plan("https://example.com/x", make_response(304))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        config = ConnectorConfig()

        first = client.get("https://example.com/x", config)
        assert first.etag == '"abc"'

        second = client.get("https://example.com/x", config, etag=first.etag)
        assert second.not_modified
        assert transport.requests_made[1]["headers"]["If-None-Match"] == '"abc"'

    def test_last_modified_sent_on_second_fetch(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", make_response(
            200, body="v1",
            headers={"Last-Modified": "Mon, 20 Jul 2026 00:00:00 GMT", "Content-Type": "text/plain"},
        ))
        transport.plan("https://example.com/x", make_response(304))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        config = ConnectorConfig()

        first = client.get("https://example.com/x", config)
        second = client.get("https://example.com/x", config, last_modified=first.last_modified)
        assert second.not_modified
        assert transport.requests_made[1]["headers"]["If-Modified-Since"] == "Mon, 20 Jul 2026 00:00:00 GMT"

    def test_stale_detection(self):
        from collector_intelligence.connector_cache import CacheEntry
        old_entry = CacheEntry(
            url="u", body="b", content_hash="h",
            fetched_at="2020-01-01T00:00:00+00:00",
        )
        assert is_stale(old_entry, ttl_seconds=60, now=datetime.now(timezone.utc))
        fresh_entry = CacheEntry(
            url="u", body="b", content_hash="h",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        assert not is_stale(fresh_entry, ttl_seconds=3600, now=datetime.now(timezone.utc))


# ---------------------------------------------------------------
# Retry / error handling
# ---------------------------------------------------------------

class TestRetryAndErrorHandling:
    def test_retries_on_5xx_then_succeeds(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", make_response(503))
        transport.plan("https://example.com/x", make_response(200, body="ok", headers={"Content-Type": "text/plain"}))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig(max_retries=2))
        assert result.success
        assert result.attempts == 2

    def test_429_retries_respecting_retry_after(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", make_response(429, headers={"Retry-After": "0"}))
        transport.plan("https://example.com/x", make_response(200, body="ok", headers={"Content-Type": "text/plain"}))
        slept = []
        client = HTTPClient(transport=transport, sleep_fn=lambda s: slept.append(s))
        result = client.get("https://example.com/x", ConnectorConfig(max_retries=2))
        assert result.success
        assert slept == [0.0]

    def test_persistent_5xx_fails_as_temporary(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", [make_response(500)] * 5)
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig(max_retries=2))
        assert not result.success
        assert result.error.error_type == "TEMPORARY_FAILURE"
        assert result.error.recoverable

    def test_timeout_retries_then_fails(self):
        from collector_intelligence.http_client import TransportTimeout
        transport = FakeTransport()
        transport.plan("https://example.com/x", [TransportTimeout("timed out")] * 5)
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig(max_retries=1))
        assert not result.success
        assert result.error.error_type == "TIMEOUT"

    def test_network_failure(self):
        from collector_intelligence.http_client import TransportNetworkError
        transport = FakeTransport()
        transport.plan("https://example.com/x", [TransportNetworkError("dns failure")] * 5)
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig(max_retries=1))
        assert not result.success
        assert result.error.error_type == "NETWORK"

    def test_ssl_failure_is_not_retried(self):
        from collector_intelligence.http_client import TransportSSLError
        transport = FakeTransport()
        transport.plan("https://example.com/x", TransportSSLError("bad cert"))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig(max_retries=3))
        assert not result.success
        assert result.error.error_type == "SSL_FAILURE"
        assert not result.error.recoverable

    def test_redirect_followed(self):
        transport = FakeTransport()
        transport.plan("https://example.com/a", make_response(302, headers={"Location": "https://example.com/b"}))
        transport.plan("https://example.com/b", make_response(200, body="final", headers={"Content-Type": "text/plain"}))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/a", ConnectorConfig())
        assert result.success
        assert result.redirect_chain == ["https://example.com/a", "https://example.com/b"]

    def test_redirect_loop_detected(self):
        transport = FakeTransport()
        transport.plan("https://example.com/a", make_response(302, headers={"Location": "https://example.com/b"}))
        transport.plan("https://example.com/b", make_response(302, headers={"Location": "https://example.com/a"}))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/a", ConnectorConfig())
        assert not result.success
        assert result.error.error_type == "REDIRECT_LOOP"

    def test_oversized_payload_rejected(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", make_response(
            200, body="x" * 1000, headers={"Content-Type": "text/plain"},
        ))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig(max_payload_bytes=100))
        assert not result.success
        assert result.error.error_type == "OVERSIZED_PAYLOAD"

    def test_unsupported_content_type_rejected(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", make_response(
            200, body="binary-ish", headers={"Content-Type": "application/octet-stream"},
        ))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig())
        assert not result.success
        assert result.error.error_type == "UNSUPPORTED_CONTENT_TYPE"

    def test_permanent_failure_not_retried(self):
        transport = FakeTransport()
        transport.plan("https://example.com/x", make_response(404))
        client = HTTPClient(transport=transport, sleep_fn=lambda s: None)
        result = client.get("https://example.com/x", ConnectorConfig(max_retries=3))
        assert not result.success
        assert result.error.error_type == "PERMANENT_FAILURE"
        assert len(transport.requests_made) == 1  # never retried


# ---------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------

class TestChangeDetection:
    def test_new_page(self):
        cache = MemoryCache()
        result = detect_change("https://example.com/x", "content", cache)
        assert result.status == "NEW"

    def test_unchanged_page(self):
        cache = MemoryCache()
        detect_change("https://example.com/x", "content", cache)
        from collector_intelligence.connector_cache import CacheEntry
        cache.set("https://example.com/x", CacheEntry(
            url="https://example.com/x", body="content",
            content_hash=compute_content_hash("content"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        ))
        result = detect_change("https://example.com/x", "content", cache)
        assert result.status == "UNCHANGED"

    def test_changed_page(self):
        cache = MemoryCache()
        from collector_intelligence.connector_cache import CacheEntry
        cache.set("https://example.com/x", CacheEntry(
            url="https://example.com/x", body=fx.CHANGED_PAGE_V1,
            content_hash=compute_content_hash(fx.CHANGED_PAGE_V1),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        ))
        result = detect_change("https://example.com/x", fx.CHANGED_PAGE_V2, cache)
        assert result.status == "CHANGED"

    def test_removed_page(self):
        cache = MemoryCache()
        from collector_intelligence.connector_cache import CacheEntry
        cache.set("https://example.com/x", CacheEntry(
            url="https://example.com/x", body="content",
            content_hash=compute_content_hash("content"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        ))
        result = detect_change("https://example.com/x", "", cache)
        assert result.status == "REMOVED"

    def test_duplicate_page_across_urls(self):
        cache = MemoryCache()
        from collector_intelligence.connector_cache import CacheEntry
        cache.set("https://example.com/original", CacheEntry(
            url="https://example.com/original", body="shared content",
            content_hash=compute_content_hash("shared content"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        ))
        result = detect_change("https://example.com/mirror", "shared content", cache)
        assert result.status == "DUPLICATE"

    def test_timestamp_only_change(self):
        cache = MemoryCache()
        from collector_intelligence.connector_cache import CacheEntry
        v1 = "Page content. Last checked: 2026-07-20T00:00:00Z"
        v2 = "Page content. Last checked: 2026-07-21T00:00:00Z"
        cache.set("https://example.com/x", CacheEntry(
            url="https://example.com/x", body=v1, content_hash=compute_content_hash(v1),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        ))
        result = detect_change("https://example.com/x", v2, cache)
        assert result.status == "TIMESTAMP_ONLY"

    def test_duplicate_fetch_skips_reingestion(self):
        client, _ = client_for({
            "https://example.com/page": [
                html_response(fx.UNCHANGED_PAGE),
                html_response(fx.UNCHANGED_PAGE),
            ],
        })
        connector = HTMLConnector()
        cache = MemoryCache()
        config = ConnectorConfig()
        descriptor = {"url": "https://example.com/page", "type": "html"}

        first = run_connector(connector, descriptor, http_client=client, cache=cache, config=config, ingest_fn=ingest_fn)
        second = run_connector(connector, descriptor, http_client=client, cache=cache, config=config, ingest_fn=ingest_fn)

        assert first.items_parsed == 1
        assert second.items_parsed == 0
        assert second.change_detection.status == "UNCHANGED"


# ---------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------

class TestScheduler:
    def test_manual_and_disabled_have_no_next_run(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        assert compute_next_run(ScheduleState(mode="manual"), now) is None
        assert compute_next_run(ScheduleState(mode="disabled"), now) is None

    def test_hourly_and_daily(self):
        now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
        hourly = compute_next_run(ScheduleState(mode="hourly"), now)
        daily = compute_next_run(ScheduleState(mode="daily"), now)
        assert hourly == "2026-07-20T11:00:00+00:00"
        assert daily == "2026-07-21T10:00:00+00:00"

    def test_cron_expression(self):
        now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
        next_run = compute_next_run(
            ScheduleState(mode="cron", cron_expression="0 9 * * *"), now,
        )
        assert next_run == "2026-07-21T09:00:00+00:00"

    def test_invalid_cron_mode_without_expression_raises(self):
        import pytest
        with pytest.raises(ValueError):
            compute_next_run(ScheduleState(mode="cron", cron_expression=None))

    def test_backoff_increases_and_caps(self):
        values = [compute_backoff_seconds(n, base_seconds=60, max_seconds=600) for n in range(1, 8)]
        assert values == sorted(values)
        assert values[-1] == 600

    def test_failure_then_success_resets_backoff(self):
        now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
        schedule = ScheduleState(mode="hourly")
        after_fail = record_run_outcome(schedule, success=False, now=now)
        assert after_fail.failure_count == 1
        assert after_fail.backoff_until is not None

        after_success = record_run_outcome(after_fail, success=True, now=now)
        assert after_success.failure_count == 0
        assert after_success.backoff_until is None


# ---------------------------------------------------------------
# Connector registry / manager
# ---------------------------------------------------------------

class TestConnectorRegistryAndManager:
    def test_registration_and_listing(self):
        manager = ConnectorManager()
        manager.register(RSSConnector())
        assert manager.has("rss_connector")
        assert "rss_connector" in manager.list_names()

    def test_unregister(self):
        manager = ConnectorManager()
        manager.register(RSSConnector())
        manager.unregister("rss_connector")
        assert not manager.has("rss_connector")

    def test_unknown_connector_raises(self):
        import pytest
        manager = ConnectorManager()
        with pytest.raises(UnknownConnectorError):
            manager.get("nonexistent")

    def test_default_manager_has_all_seven_connectors(self):
        manager = build_default_manager()
        assert set(manager.list_names()) == {
            "rss_connector", "html_connector", "json_connector", "xml_connector",
            "announcement_connector", "retailer_page_connector", "event_connector",
        }

    def test_health_check_reflects_success(self):
        client, _ = client_for({"https://example.com/x": html_response("ok")})
        manager = ConnectorManager(http_client=client)
        manager.register(HTMLConnector())
        result = manager.run_connector(
            "html_connector", {"url": "https://example.com/x", "type": "html"},
            ConnectorConfig(), ingest_fn,
        )
        health = manager.get_health("html_connector")
        assert health.healthy is True
        assert health.consecutive_failures == 0

    def test_health_check_reflects_failure(self):
        client, _ = client_for({"https://example.com/x": make_response(500)})
        manager = ConnectorManager(http_client=client)
        manager.register(HTMLConnector())
        manager.run_connector(
            "html_connector", {"url": "https://example.com/x", "type": "html"},
            ConnectorConfig(max_retries=0), ingest_fn,
        )
        health = manager.get_health("html_connector")
        assert health.healthy is False
        assert health.consecutive_failures == 1

    def test_run_all_batch_execution(self):
        client, _ = client_for({
            "https://example.com/a": html_response("<html><head><title>A</title></head><body>Brand X and Partner Co launched a collaboration.</body></html>"),
            "https://example.com/b": html_response("<html><head><title>B</title></head><body>Brand X and Partner Co launched a collaboration.</body></html>"),
        })
        manager = ConnectorManager(http_client=client)
        manager.register(HTMLConnector())
        batch = manager.run_all(
            {"html_connector": [
                {"url": "https://example.com/a", "type": "html"},
                {"url": "https://example.com/b", "type": "html"},
            ]},
            ConnectorConfig(), ingest_fn,
        )
        assert batch.total_count == 2
        assert batch.success_count == 2

    def test_partial_failure_in_batch(self):
        client, _ = client_for({
            "https://example.com/a": html_response("<html><head><title>A</title></head><body>Brand X and Partner Co launched a collaboration.</body></html>"),
            "https://example.com/bad": make_response(404),
        })
        manager = ConnectorManager(http_client=client)
        manager.register(HTMLConnector())
        batch = manager.run_all(
            {"html_connector": [
                {"url": "https://example.com/a", "type": "html"},
                {"url": "https://example.com/bad", "type": "html"},
            ]},
            ConnectorConfig(max_retries=0), ingest_fn,
        )
        assert batch.success_count == 1
        assert batch.failure_count == 1

    def test_per_connector_config_override(self):
        config = ConnectorConfig(timeout_seconds=15.0, overrides={
            "rss_connector": {"timeout_seconds": 5.0},
        })
        overridden = config.for_connector("rss_connector")
        assert overridden.timeout_seconds == 5.0
        assert config.for_connector("html_connector").timeout_seconds == 15.0


# ---------------------------------------------------------------
# Pipeline-level functions
# ---------------------------------------------------------------

class TestPipelineFunctions:
    def test_fetch_source(self):
        client, _ = client_for({"https://example.com/x": html_response("hello")})
        result = fetch_source("https://example.com/x", config=ConnectorConfig(), http_client=client)
        assert result.success
        assert result.body == "hello"

    def test_fetch_batch(self):
        client, _ = client_for({
            "https://example.com/a": html_response("a"),
            "https://example.com/b": html_response("b"),
        })
        results = fetch_batch(
            ["https://example.com/a", "https://example.com/b"],
            config=ConnectorConfig(), http_client=client,
        )
        assert all(r.success for r in results)

    def test_run_connector_batch(self):
        client, _ = client_for({
            "https://example.com/a": html_response("<html><head><title>A</title></head><body>Brand X and Partner Co launched a collaboration.</body></html>"),
            "https://example.com/b": html_response("<html><head><title>B</title></head><body>Brand X and Partner Co launched a collaboration.</body></html>"),
        })
        batch = run_connector_batch(
            HTMLConnector(),
            [{"url": "https://example.com/a", "type": "html"}, {"url": "https://example.com/b", "type": "html"}],
            http_client=client, ingest_fn=ingest_fn,
        )
        assert batch.total_count == 2
        assert batch.success_count == 2


# ---------------------------------------------------------------
# Full pipeline integration: Connector -> Module 5 -> Module 2 -> Module 4
# ---------------------------------------------------------------

class TestFullPipelineIntegration:
    def test_round1_official_announcement(self):
        client, _ = client_for({"https://round1.example.com/news": html_response(fx.ROUND1_OFFICIAL_ANNOUNCEMENT_HTML)})
        result = run_connector(
            AnnouncementConnector(), {"url": "https://round1.example.com/news", "type": "announcement"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        from collector_intelligence.detector import detect_signals
        detection = detect_signals(result.ingestion_results[0].raw_source)
        assert detection.has_signal("COLLABORATION")

    def test_round1_retailer_fixture(self):
        client, _ = client_for({"https://round1.example.com/product": html_response(fx.ROUND1_RETAILER_PAGE_HTML)})
        result = run_connector(
            RetailerPageConnector(), {"url": "https://round1.example.com/product", "type": "retailer_page", "retailer": "Round1"},
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        assert result.ingestion_results[0].raw_source.retailer == "Round1"

    def test_round1_marketplace_fixture(self):
        client, _ = client_for({"https://example.com/listings.json": html_response(fx.ROUND1_MARKETPLACE_JSON, "application/json")})
        result = run_connector(
            JSONConnector(),
            {
                "url": "https://example.com/listings.json", "type": "json",
                "adapter_target": "marketplace_listing", "items_path": ["listings"],
            },
            http_client=client, ingest_fn=ingest_fn,
        )
        assert result.success
        raw_source = result.ingestion_results[0].raw_source
        assert "sold for $2200" in raw_source.body
        assert "complete set" in raw_source.body

    def test_combined_round1_reaches_module_4(self):
        client, _ = client_for({
            "https://round1.example.com/news": html_response(fx.ROUND1_OFFICIAL_ANNOUNCEMENT_HTML),
            "https://round1.example.com/product": html_response(fx.ROUND1_RETAILER_PAGE_HTML),
            "https://example.com/listings.json": html_response(fx.ROUND1_MARKETPLACE_JSON, "application/json"),
        })

        run_results = [
            run_connector(
                AnnouncementConnector(), {"url": "https://round1.example.com/news", "type": "announcement"},
                http_client=client, ingest_fn=ingest_fn,
            ),
            run_connector(
                RetailerPageConnector(), {"url": "https://round1.example.com/product", "type": "retailer_page", "retailer": "Round1"},
                http_client=client, ingest_fn=ingest_fn,
            ),
            run_connector(
                JSONConnector(),
                {"url": "https://example.com/listings.json", "type": "json", "adapter_target": "marketplace_listing", "items_path": ["listings"]},
                http_client=client, ingest_fn=ingest_fn,
            ),
        ]

        assert all(r.success for r in run_results)

        finalization = process_connector_run_results(run_results)
        assert finalization is not None
        assert finalization.group_count == 1

        finalized = finalization.finalized_opportunities[0]
        assert finalized.opportunity.recent_sold_price == 2200.0
        assert finalized.evaluation.recommendation != "CRITICAL_BUY"

    def test_failed_fetch_excluded_from_finalization(self):
        client, _ = client_for({
            "https://round1.example.com/news": html_response(fx.ROUND1_OFFICIAL_ANNOUNCEMENT_HTML),
            "https://example.com/broken": make_response(404),
        })
        run_results = [
            run_connector(
                AnnouncementConnector(), {"url": "https://round1.example.com/news", "type": "announcement"},
                http_client=client, ingest_fn=ingest_fn,
            ),
            run_connector(
                HTMLConnector(), {"url": "https://example.com/broken", "type": "html"},
                http_client=client, config=ConnectorConfig(max_retries=0), ingest_fn=ingest_fn,
            ),
        ]
        finalization = process_connector_run_results(run_results)
        assert finalization.total_sources == 1


# ---------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_parse_output(self):
        parsed_a = parse_rss_or_atom(fx.ROUND1_RSS_FEED_XML)
        parsed_b = parse_rss_or_atom(fx.ROUND1_RSS_FEED_XML)
        assert parsed_a == parsed_b

    def test_deterministic_fingerprint_via_content_hash(self):
        assert compute_content_hash(fx.CHANGED_PAGE_V1) == compute_content_hash(fx.CHANGED_PAGE_V1)
        assert compute_content_hash(fx.CHANGED_PAGE_V1) != compute_content_hash(fx.CHANGED_PAGE_V2)
