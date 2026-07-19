"""
End-to-end regression test for the Pokémon restock-suppression bug.

Unlike tests/test_pokemon_collector.py (which stubs out save_opportunity
entirely), this test runs PokemonScout.run() against a real
AtlasScout.save_opportunity() / opportunity_exists() implementation, with
only the Supabase HTTP calls mocked. It proves that a later, genuinely
distinct Pokémon event (SOLD_OUT, then RESTOCK) for a product that
already has a prior opportunity row with the exact same official_url and
item_name still reaches the fake Supabase backend as its own row - which
is exactly the scenario that was previously silently suppressed by
AtlasScout.opportunity_exists()'s URL/title-only dedup check - and that
idempotency is enforced by Supabase itself (via event_key), not merely
assumed from local bookkeeping.
"""

import scouts.base.atlas_scout as atlas_scout_module
from scouts.pokemon.alert_store import PokemonAlertStore
from scouts.pokemon.collector import PokemonScout
from scouts.pokemon.release_store import PokemonReleaseStore
from scouts.pokemon.state_tracker import PokemonStateTracker
from scouts.tcg.catalog_store import TcgCatalogStore


class FakeSupabaseOpportunities:
    """
    Simulates the partial unique index on event_key: a POST whose
    event_key already exists on a stored row is rejected with HTTP
    409 and not inserted, mirroring Postgres's unique_violation
    behavior via PostgREST.
    """

    def __init__(self):
        self.rows = []
        self.get_calls = []
        self._next_id = 1

    def get(self, url, headers, params, timeout=None):
        self.get_calls.append(dict(params))

        matches = self.rows

        if "event_key" in params:
            value = params["event_key"].removeprefix(
                "eq."
            )
            matches = [
                row
                for row in matches
                if row.get("event_key") == value
            ]

        if "official_url" in params:
            value = params["official_url"].removeprefix(
                "eq."
            )
            matches = [
                row
                for row in matches
                if row.get("official_url") == value
            ]

        if "item_name" in params:
            value = params["item_name"].removeprefix(
                "eq."
            )
            matches = [
                row
                for row in matches
                if row.get("item_name") == value
            ]

        return FakeResponse(
            [{"id": row["id"]} for row in matches]
        )

    def post(self, url, headers, json, timeout=None):
        event_key = json.get("event_key")

        if event_key is not None and any(
            row.get("event_key") == event_key
            for row in self.rows
        ):
            return FakeResponse(
                {"code": "23505"},
                status_code=409,
            )

        row = dict(json)
        row["id"] = self._next_id
        self._next_id += 1
        self.rows.append(row)
        return FakeResponse([row])


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise atlas_scout_module.requests.HTTPError(
                f"HTTP {self.status_code}"
            )

    def json(self):
        return self._payload


def make_scout(monkeypatch, tmp_path, fake_supabase, availability_sequence):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SERVICE_KEY",
        "test-service-key",
    )
    monkeypatch.setenv(
        "ATLAS_LEARNING_PATH",
        str(tmp_path / "learning_history.json"),
    )

    monkeypatch.setattr(
        atlas_scout_module.requests,
        "get",
        fake_supabase.get,
    )
    monkeypatch.setattr(
        atlas_scout_module.requests,
        "post",
        fake_supabase.post,
    )

    call_index = {"value": 0}

    def fake_collector():
        availability = availability_sequence[
            call_index["value"]
        ]
        call_index["value"] += 1

        return [{
            "title": "Pokémon Center Regression ETB",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/regression-etb"
            ),
            "sku": "SKU-REGRESSION",
            "availability": availability,
        }]

    def fake_enricher(item):
        return {
            **item,
            "category": "pokemon",
            "collector_score": 50,
            "popularity_score": 50,
            "flip_score": 40,
            "hold_score": 40,
            "sleeper_score": 15,
            "consensus_score": 30,
            "best_strategy": {
                "strategy": "WATCH",
                "score": 40,
            },
        }

    scout = PokemonScout(
        collector=fake_collector,
        enricher=fake_enricher,
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


def test_restock_after_sold_out_reaches_fake_supabase_as_a_new_row(
    monkeypatch,
    tmp_path,
):
    fake_supabase = FakeSupabaseOpportunities()

    scout = make_scout(
        monkeypatch,
        tmp_path,
        fake_supabase,
        availability_sequence=[
            "InStock",
            "OutOfStock",
            "InStock",
        ],
    )

    scout.run()  # NEW_PRODUCT
    assert len(fake_supabase.rows) == 1

    scout.run()  # SOLD_OUT
    assert len(fake_supabase.rows) == 2

    scout.run()  # RESTOCK - the reported bug scenario
    assert len(fake_supabase.rows) == 3

    # The defining proof: all three rows share the identical,
    # customer-facing product URL and title - nothing was corrupted
    # or replaced to force uniqueness - yet three distinct rows exist,
    # each with its own event_key.
    urls = {row["official_url"] for row in fake_supabase.rows}
    names = {row["item_name"] for row in fake_supabase.rows}
    event_keys = {row["event_key"] for row in fake_supabase.rows}
    assert urls == {
        "https://www.pokemoncenter.com/"
        "product/regression-etb"
    }
    assert names == {"Pokémon Center Regression ETB"}
    assert len(event_keys) == 3

    events = sorted(
        alert["event"]
        for alert in scout.alert_store.all()
    )
    assert events == [
        "NEW_PRODUCT",
        "RESTOCK",
        "SOLD_OUT",
    ]
    assert all(
        alert["opportunity_forwarded"] is True
        for alert in scout.alert_store.all()
    )


def test_unmodified_opportunity_exists_would_have_blocked_the_restock(
    monkeypatch,
    tmp_path,
):
    """
    Proves the fix works by routing around the existing check, not by
    weakening it: at the moment of the restock, calling the original,
    untouched opportunity_exists() directly on the same item still
    correctly reports a duplicate by URL - confirming the underlying
    product-level check was never modified.
    """

    fake_supabase = FakeSupabaseOpportunities()

    scout = make_scout(
        monkeypatch,
        tmp_path,
        fake_supabase,
        availability_sequence=[
            "InStock",
            "OutOfStock",
            "InStock",
        ],
    )

    scout.run()  # NEW_PRODUCT
    scout.run()  # SOLD_OUT

    restock_item = {
        "title": "Pokémon Center Regression ETB",
        "url": (
            "https://www.pokemoncenter.com/"
            "product/regression-etb"
        ),
        "brand": "Pokemon",
    }

    assert scout.opportunity_exists(restock_item) is True

    scout.run()  # RESTOCK still succeeds via event_key
    assert len(fake_supabase.rows) == 3


def test_repeated_polling_of_unchanged_state_creates_no_further_rows(
    monkeypatch,
    tmp_path,
):
    fake_supabase = FakeSupabaseOpportunities()

    scout = make_scout(
        monkeypatch,
        tmp_path,
        fake_supabase,
        availability_sequence=[
            "InStock",
            "InStock",
            "InStock",
        ],
    )

    scout.run()  # NEW_PRODUCT
    assert len(fake_supabase.rows) == 1

    scout.run()  # NO_CHANGE
    scout.run()  # NO_CHANGE

    # No duplicate opportunity rows, and therefore no duplicate
    # notifications/Discord messages for the same event, since
    # atlas/create_notifications.py creates exactly one notification
    # per opportunity row.
    assert len(fake_supabase.rows) == 1


def test_local_forwarded_mark_failure_after_successful_insert_does_not_duplicate(
    monkeypatch,
    tmp_path,
):
    """
    This is the exact race the previous dedup_key-bypass design got
    wrong: save_opportunity() succeeds and inserts a row, but the
    local opportunity_forwarded flag then fails to persist (simulated
    by monkeypatching PokemonAlertStore.mark_opportunity_forwarded to
    raise). On the next scan, the same alert record is still locally
    "unforwarded" and gets retried - but because Supabase itself now
    enforces uniqueness on event_key, the retry correctly returns
    False instead of inserting a second row.
    """

    fake_supabase = FakeSupabaseOpportunities()

    scout = make_scout(
        monkeypatch,
        tmp_path,
        fake_supabase,
        availability_sequence=[
            "InStock",
            "InStock",
        ],
    )

    original_mark = PokemonAlertStore.mark_opportunity_forwarded
    call_count = {"value": 0}

    def flaky_mark(self, alert_id):
        call_count["value"] += 1

        if call_count["value"] == 1:
            raise OSError(
                "disk full while marking forwarded"
            )

        return original_mark(self, alert_id)

    monkeypatch.setattr(
        PokemonAlertStore,
        "mark_opportunity_forwarded",
        flaky_mark,
    )

    scout.run()

    # The insert succeeded in fake Supabase...
    assert len(fake_supabase.rows) == 1

    # ...but the local flag failed to persist, so the record still
    # looks "unforwarded" locally.
    alert = scout.alert_store.all()[0]
    assert alert["opportunity_forwarded"] is False

    # Second scan (state unchanged, so no fresh alert - the retry
    # comes from the still-active, locally-unforwarded record).
    scout.run()

    # Supabase's event_key uniqueness prevents a second row from
    # ever being created for the same event, regardless of what the
    # local flag says.
    assert len(fake_supabase.rows) == 1

    # And the retry's False result now correctly self-heals the
    # local flag, since a False with an event_key set proves the
    # event was already persisted.
    alert = scout.alert_store.all()[0]
    assert alert["opportunity_forwarded"] is True


def test_temporary_supabase_failure_retries_successfully(
    monkeypatch,
    tmp_path,
):
    fake_supabase = FakeSupabaseOpportunities()

    scout = make_scout(
        monkeypatch,
        tmp_path,
        fake_supabase,
        availability_sequence=[
            "InStock",
            "InStock",
        ],
    )

    real_post = fake_supabase.post
    call_count = {"value": 0}

    def flaky_post(url, headers, json, timeout=None):
        call_count["value"] += 1

        if call_count["value"] == 1:
            raise atlas_scout_module.requests.ConnectionError(
                "temporary network failure"
            )

        return real_post(
            url, headers, json, timeout=timeout
        )

    monkeypatch.setattr(
        atlas_scout_module.requests,
        "post",
        flaky_post,
    )

    scout.run()
    assert len(fake_supabase.rows) == 0

    alert = scout.alert_store.all()[0]
    assert alert["opportunity_forwarded"] is False

    scout.run()
    assert len(fake_supabase.rows) == 1

    alert = scout.alert_store.all()[0]
    assert alert["opportunity_forwarded"] is True
