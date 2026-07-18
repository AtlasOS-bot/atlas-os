from scouts.pokemon.alert_store import (
    PokemonAlertStore,
)
from scouts.pokemon.collector import (
    PokemonScout,
)
from scouts.pokemon.enrichment import (
    enrich_pokemon_item,
)
from scouts.pokemon.internet_scout import (
    collect_official_pokemon_items,
)
from scouts.pokemon.release_store import (
    PokemonReleaseStore,
)
from scouts.pokemon.state_tracker import (
    PokemonStateTracker,
)
from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)


def make_scout(
    monkeypatch,
    tmp_path,
    collector=None,
    enricher=None,
):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SERVICE_KEY",
        "test-service-key",
    )

    scout = PokemonScout(
        collector=collector,
        enricher=enricher,
    )

    scout.state_tracker = PokemonStateTracker(
        path=tmp_path / "pokemon_states.json"
    )
    scout.alert_store = PokemonAlertStore(
        path=tmp_path / "pokemon_alerts.json"
    )
    scout.release_store = PokemonReleaseStore(
        path=tmp_path / "pokemon_releases.json"
    )
    scout.catalog_store = TcgCatalogStore(
        path=tmp_path / "tcg_catalog.json"
    )

    return scout


def basic_enriched_fields(
    collector_score=50,
    popularity_score=50,
    flip_score=40,
    hold_score=40,
    sleeper_score=15,
    consensus_score=30,
    strategy="WATCH",
    strategy_score=40,
):
    return {
        "category": "pokemon",
        "collector_score": collector_score,
        "popularity_score": popularity_score,
        "flip_score": flip_score,
        "hold_score": hold_score,
        "sleeper_score": sleeper_score,
        "consensus_score": consensus_score,
        "best_strategy": {
            "strategy": strategy,
            "score": strategy_score,
        },
    }


def test_successful_full_run_processes_all_items(
    monkeypatch,
    tmp_path,
):
    raw_items = [
        {
            "title": "Pokémon Center ETB Alpha",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/etb-alpha"
            ),
            "sku": "SKU-A",
        },
        {
            "title": "Pokémon Center ETB Beta",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/etb-beta"
            ),
            "sku": "SKU-B",
        },
    ]

    def fake_collector():
        return raw_items

    def fake_enricher(item):
        return {
            **item,
            **basic_enriched_fields(
                collector_score=80,
                popularity_score=75,
                flip_score=60,
                hold_score=70,
                consensus_score=50,
                strategy="HOLD",
                strategy_score=70,
            ),
        }

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=fake_collector,
        enricher=fake_enricher,
    )

    saved_titles = []

    def fake_save_opportunity(item):
        saved_titles.append(item["title"])
        return True

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    items = scout.run()

    assert len(items) == 2

    assert saved_titles == [
        "Pokémon Center ETB Alpha",
        "Pokémon Center ETB Beta",
    ]

    catalog = scout.catalog_store.load()
    assert catalog["count"] == 2

    releases = scout.release_store.load()
    assert releases["count"] == 2

    alerts = scout.alert_store.all()
    assert len(alerts) == 2
    assert {
        alert["event"] for alert in alerts
    } == {"NEW_PRODUCT"}


def test_partial_source_results_are_processed_normally(
    monkeypatch,
    tmp_path,
):
    """
    Real per-source network failures are already isolated at the
    acquisition layer (acquisition/requests_retriever.py catches
    requests.RequestException per source and acquisition/service.py
    continues to the next source regardless). This test proves that
    PokemonScout correctly consumes a partial result set produced by
    that isolation instead of requiring every source to have
    succeeded.
    """

    def fake_collector():
        collected = []

        for source in [
            "pokemon_news",
            "pokemon_center_new_releases",
        ]:
            if source == "pokemon_news":
                continue

            collected.append({
                "title": (
                    "Pokémon Center Booster Bundle"
                ),
                "url": (
                    "https://www.pokemoncenter.com/"
                    "product/booster-bundle"
                ),
                "sku": "SKU-BB",
                "sources": [source],
            })

        return collected

    def fake_enricher(item):
        return {
            **item,
            **basic_enriched_fields(),
        }

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=fake_collector,
        enricher=fake_enricher,
    )

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        lambda item: True,
    )

    items = scout.run()

    assert len(items) == 1
    assert (
        items[0]["title"]
        == "Pokémon Center Booster Bundle"
    )


def test_total_collection_failure_does_not_crash_run(
    monkeypatch,
    tmp_path,
    capsys,
):
    def failing_collector():
        raise ConnectionError(
            "all sources unreachable"
        )

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=failing_collector,
    )

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        lambda item: True,
    )

    items = scout.run()

    assert items == []

    releases = scout.release_store.load()
    assert releases["count"] == 0

    catalog = scout.catalog_store.load()
    assert catalog["count"] == 0

    captured = capsys.readouterr()
    assert (
        "[PokemonScout] collection failed"
        in captured.out
    )
    assert "ConnectionError" in captured.out


def test_malformed_item_does_not_stop_remaining_items(
    monkeypatch,
    tmp_path,
    capsys,
):
    raw_items = [
        "not-a-valid-item",
        {
            "title": "Pokémon Center Tin",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/tin"
            ),
            "sku": "SKU-TIN",
        },
    ]

    def fake_collector():
        return raw_items

    def fake_enricher(item):
        if not isinstance(item, dict):
            raise TypeError(
                "cannot enrich a non-dict item"
            )

        return {
            **item,
            **basic_enriched_fields(),
        }

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=fake_collector,
        enricher=fake_enricher,
    )

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        lambda item: True,
    )

    items = scout.run()

    assert len(items) == 1
    assert items[0]["title"] == "Pokémon Center Tin"

    captured = capsys.readouterr()
    assert (
        "[PokemonScout] enrichment failed"
        in captured.out
    )
    assert "TypeError" in captured.out


def test_enricher_failure_for_one_item_does_not_stop_others(
    monkeypatch,
    tmp_path,
    capsys,
):
    raw_items = [
        {
            "title": "Pokémon Center Plush",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/plush"
            ),
            "sku": "SKU-PLUSH",
        },
        {
            "title": "Pokémon Center Figure",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/figure"
            ),
            "sku": "SKU-FIGURE",
        },
    ]

    def fake_collector():
        return raw_items

    def flaky_enricher(item):
        if item["sku"] == "SKU-PLUSH":
            raise ValueError(
                "enrichment pipeline exploded "
                "for this item"
            )

        return {
            **item,
            **basic_enriched_fields(),
        }

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=fake_collector,
        enricher=flaky_enricher,
    )

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        lambda item: True,
    )

    items = scout.run()

    assert len(items) == 1
    assert items[0]["sku"] == "SKU-FIGURE"

    captured = capsys.readouterr()
    assert (
        "[PokemonScout] enrichment failed "
        "(Pokémon Center Plush)"
        in captured.out
    )
    assert "ValueError" in captured.out


def test_release_calendar_persistence_failure_does_not_crash_run(
    monkeypatch,
    tmp_path,
    capsys,
):
    raw_items = [
        {
            "title": "Pokémon Center Bundle",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/bundle"
            ),
            "sku": "SKU-BUNDLE",
        },
    ]

    def fake_collector():
        return raw_items

    def fake_enricher(item):
        return {
            **item,
            **basic_enriched_fields(),
        }

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=fake_collector,
        enricher=fake_enricher,
    )

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        lambda item: True,
    )

    def failing_save(items):
        raise OSError("disk full")

    monkeypatch.setattr(
        scout.release_store,
        "save",
        failing_save,
    )

    items = scout.run()

    assert len(items) == 1

    catalog = scout.catalog_store.load()
    assert catalog["count"] == 1

    alerts = scout.alert_store.all()
    assert len(alerts) == 1

    captured = capsys.readouterr()
    assert (
        "[PokemonScout] release_calendar failed"
        in captured.out
    )
    assert "disk full" in captured.out


def test_alert_persistence_failure_does_not_prevent_remaining_processing(
    monkeypatch,
    tmp_path,
    capsys,
):
    raw_items = [
        {
            "title": (
                "Pokémon Center Poster Collection"
            ),
            "url": (
                "https://www.pokemoncenter.com/"
                "product/poster"
            ),
            "sku": "SKU-POSTER",
        },
        {
            "title": "Pokémon Center Binder",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/binder"
            ),
            "sku": "SKU-BINDER",
        },
    ]

    def fake_collector():
        return raw_items

    def fake_enricher(item):
        return {
            **item,
            **basic_enriched_fields(),
        }

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=fake_collector,
        enricher=fake_enricher,
    )

    saved_titles = []

    def fake_save_opportunity(item):
        saved_titles.append(item["title"])
        return True

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    def failing_alert_save(item, alert):
        raise RuntimeError(
            "alert store unavailable"
        )

    monkeypatch.setattr(
        scout.alert_store,
        "save",
        failing_alert_save,
    )

    items = scout.run()

    assert len(items) == 2

    assert saved_titles == [
        "Pokémon Center Poster Collection",
        "Pokémon Center Binder",
    ]

    catalog = scout.catalog_store.load()
    assert catalog["count"] == 2

    captured = capsys.readouterr()
    assert (
        captured.out.count(
            "[PokemonScout] alert_persistence failed"
        )
        == 2
    )


def test_injected_collector_and_enricher_are_used(
    monkeypatch,
    tmp_path,
):
    calls = {
        "collector": 0,
        "enricher": 0,
    }

    def fake_collector():
        calls["collector"] += 1

        return [{
            "title": "Injected Item",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/injected"
            ),
            "sku": "SKU-INJECTED",
        }]

    def fake_enricher(item):
        calls["enricher"] += 1

        return {
            **item,
            **basic_enriched_fields(),
        }

    scout = make_scout(
        monkeypatch,
        tmp_path,
        collector=fake_collector,
        enricher=fake_enricher,
    )

    items = scout.collect()

    assert calls == {
        "collector": 1,
        "enricher": 1,
    }

    assert len(items) == 1
    assert items[0]["title"] == "Injected Item"


def test_default_construction_uses_default_collector_and_enricher(
    monkeypatch,
):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SERVICE_KEY",
        "test-service-key",
    )

    scout = PokemonScout()

    assert (
        scout.collector
        is collect_official_pokemon_items
    )
    assert (
        scout.enricher is enrich_pokemon_item
    )
    assert scout.brand == "Pokemon"
    assert scout.category == "pokemon"
    assert isinstance(
        scout.state_tracker,
        PokemonStateTracker,
    )
    assert isinstance(
        scout.alert_store,
        PokemonAlertStore,
    )
    assert isinstance(
        scout.release_store,
        PokemonReleaseStore,
    )
    assert isinstance(
        scout.catalog_store,
        TcgCatalogStore,
    )
