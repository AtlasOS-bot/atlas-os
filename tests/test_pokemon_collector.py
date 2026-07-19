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

    def fake_save_opportunity(item, event_key=None):
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
        lambda item, event_key=None: True,
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
        lambda item, event_key=None: True,
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
        lambda item, event_key=None: True,
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
        lambda item, event_key=None: True,
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
        lambda item, event_key=None: True,
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

    def fake_save_opportunity(item, event_key=None):
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

    # Opportunity forwarding is gated on having a persisted, trackable
    # alert-event record (see _resolve_eligible_alert_record). When alert
    # persistence itself always fails, there is no reliable event identity
    # to forward against or later mark as forwarded, so save_opportunity
    # is correctly never attempted here. This is intentional: forwarding
    # without a trackable record would risk re-forwarding the same event
    # on every future scan, which is exactly the bug this gating exists
    # to prevent. Item iteration and catalog persistence remain isolated
    # from the alert-persistence failure regardless.
    assert saved_titles == []

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


def make_flappable_item(availability):
    return {
        "title": "Pokémon Center Flap ETB",
        "url": (
            "https://www.pokemoncenter.com/"
            "product/flap-etb"
        ),
        "sku": "SKU-FLAP",
        "availability": availability,
    }


def test_new_product_forwards_one_opportunity(
    monkeypatch,
    tmp_path,
):
    def fake_collector():
        return [
            make_flappable_item("InStock")
        ]

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

    save_calls = []

    def fake_save_opportunity(item, event_key=None):
        save_calls.append(item["title"])
        return True

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    scout.run()

    assert save_calls == [
        "Pokémon Center Flap ETB"
    ]

    alerts = scout.alert_store.all()
    assert len(alerts) == 1
    assert alerts[0]["event"] == "NEW_PRODUCT"
    assert (
        alerts[0]["opportunity_forwarded"]
        is True
    )


def test_repeated_observation_of_same_event_does_not_forward_again(
    monkeypatch,
    tmp_path,
):
    def fake_collector():
        return [
            make_flappable_item("InStock")
        ]

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

    save_calls = []

    def fake_save_opportunity(item, event_key=None):
        save_calls.append(item["title"])
        return True

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    scout.run()

    assert len(save_calls) == 1

    # Second scan: identical availability, so state_tracker reports
    # NO_CHANGE and no fresh alert is created. The prior NEW_PRODUCT
    # alert is already forwarded, so it must not be forwarded again.
    scout.run()

    assert len(save_calls) == 1


def test_later_distinct_restock_after_sold_out_can_forward(
    monkeypatch,
    tmp_path,
):
    availability_sequence = [
        "InStock",
        "OutOfStock",
        "InStock",
    ]

    call_index = {"value": 0}

    def fake_collector():
        availability = availability_sequence[
            call_index["value"]
        ]
        call_index["value"] += 1
        return [
            make_flappable_item(availability)
        ]

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

    save_calls = []

    def fake_save_opportunity(item, event_key=None):
        save_calls.append(item["title"])
        return True

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    scout.run()
    assert len(save_calls) == 1  # NEW_PRODUCT

    scout.run()
    assert len(save_calls) == 2  # SOLD_OUT

    scout.run()
    assert len(save_calls) == 3  # RESTOCK

    alerts = scout.alert_store.all()
    events = sorted(
        alert["event"] for alert in alerts
    )
    assert events == [
        "NEW_PRODUCT",
        "RESTOCK",
        "SOLD_OUT",
    ]
    assert all(
        alert["opportunity_forwarded"] is True
        for alert in alerts
    )


def test_price_drop_event_follows_the_same_forwarding_rule(
    monkeypatch,
    tmp_path,
):
    def make_priced_item(price):
        return {
            "title": "Pokémon Center Price Item",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/price-item"
            ),
            "sku": "SKU-PRICE",
            "availability": "InStock",
            "retail_price": price,
        }

    price_sequence = [59.99, 39.99]
    call_index = {"value": 0}

    def fake_collector():
        price = price_sequence[
            call_index["value"]
        ]
        call_index["value"] += 1
        return [make_priced_item(price)]

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

    save_calls = []

    def fake_save_opportunity(item, event_key=None):
        save_calls.append(item["title"])
        return True

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    scout.run()
    assert len(save_calls) == 1  # NEW_PRODUCT

    scout.run()
    assert len(save_calls) == 2  # PRICE_DROP

    alerts = scout.alert_store.all()
    events = sorted(
        alert["event"] for alert in alerts
    )
    assert events == [
        "NEW_PRODUCT",
        "PRICE_DROP",
    ]
    assert all(
        alert["opportunity_forwarded"] is True
        for alert in alerts
    )


def test_successful_persistence_marks_only_the_matching_alert_event(
    monkeypatch,
    tmp_path,
):
    raw_items = [
        {
            "title": "Item Alpha",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/alpha"
            ),
            "sku": "SKU-ALPHA",
            "availability": "InStock",
        },
        {
            "title": "Item Beta",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/beta"
            ),
            "sku": "SKU-BETA",
            "availability": "InStock",
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

    def fake_save_opportunity(item, event_key=None):
        if item["title"] == "Item Alpha":
            return True

        # A real failure (not a duplicate) for Beta - this
        # must not mark Beta's alert record forwarded, and
        # must not affect Alpha's record either.
        raise ConnectionError(
            "supabase unreachable"
        )

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    scout.run()

    alerts = {
        alert["title"]: alert
        for alert in scout.alert_store.all()
    }

    assert (
        alerts["Item Alpha"][
            "opportunity_forwarded"
        ]
        is True
    )
    assert (
        alerts["Item Beta"][
            "opportunity_forwarded"
        ]
        is False
    )


def test_raised_persistence_does_not_mark_event_as_forwarded(
    monkeypatch,
    tmp_path,
    capsys,
):
    def fake_collector():
        return [
            make_flappable_item("InStock")
        ]

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

    def failing_save_opportunity(item, event_key=None):
        raise ConnectionError(
            "supabase unreachable"
        )

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        failing_save_opportunity,
    )

    scout.run()

    alerts = scout.alert_store.all()
    assert len(alerts) == 1
    assert (
        alerts[0]["opportunity_forwarded"]
        is False
    )

    captured = capsys.readouterr()
    assert (
        "[PokemonScout] reasoning_and_"
        "opportunity_persistence failed"
        in captured.out
    )


def test_failed_persistence_can_retry_successfully_on_a_later_run(
    monkeypatch,
    tmp_path,
):
    def fake_collector():
        return [
            make_flappable_item("InStock")
        ]

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

    outcomes = iter([
        ConnectionError(
            "supabase unreachable"
        ),
        True,
    ])

    save_calls = []

    def flaky_save_opportunity(item, event_key=None):
        save_calls.append(item["title"])
        outcome = next(outcomes)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        flaky_save_opportunity,
    )

    scout.run()

    alerts = scout.alert_store.all()
    assert len(alerts) == 1
    assert (
        alerts[0]["opportunity_forwarded"]
        is False
    )

    # Second scan observes the same unchanged state (NO_CHANGE), but the
    # prior alert is still unforwarded, so it must be retried.
    scout.run()

    assert len(save_calls) == 2

    alerts = scout.alert_store.all()
    assert len(alerts) == 1
    assert (
        alerts[0]["opportunity_forwarded"]
        is True
    )


def test_collector_fault_isolation_still_works_alongside_forwarding_gate(
    monkeypatch,
    tmp_path,
):
    raw_items = [
        "not-a-valid-item",
        make_flappable_item("InStock"),
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

    save_calls = []

    def fake_save_opportunity(item, event_key=None):
        save_calls.append(item["title"])
        return True

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    items = scout.run()

    assert len(items) == 1
    assert save_calls == [
        "Pokémon Center Flap ETB"
    ]


def test_duplicate_event_key_result_marks_local_record_forwarded(
    monkeypatch,
    tmp_path,
):
    """
    Explicit, isolated proof of the ordering rule: when
    save_opportunity(item, event_key=...) returns False because
    Supabase already has a row with that exact event_key, the local
    alert record must be marked forwarded immediately - this is what
    prevents the local gate from retrying the same already-persisted
    event on every future scan.
    """

    def fake_collector():
        return [
            make_flappable_item("InStock")
        ]

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

    received_event_keys = []

    def fake_save_opportunity(item, event_key=None):
        received_event_keys.append(event_key)
        # Simulate Supabase already having a row for this exact
        # event_key (e.g. inserted by an earlier, now-forgotten run).
        return False

    monkeypatch.setattr(
        scout,
        "save_opportunity",
        fake_save_opportunity,
    )

    scout.run()

    assert len(received_event_keys) == 1
    assert received_event_keys[0] is not None

    alerts = scout.alert_store.all()
    assert len(alerts) == 1
    assert (
        alerts[0]["opportunity_forwarded"] is True
    )
