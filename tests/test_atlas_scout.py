import scouts.base.atlas_scout as atlas_scout_module
from scouts.base.atlas_scout import AtlasScout
from scouts.lorcana.collector import LorcanaScout
from scouts.one_piece.collector import OnePieceScout


class FakeSupabaseOpportunities:
    """
    In-memory stand-in for the Supabase `opportunities` REST endpoint,
    used to verify AtlasScout.save_opportunity()'s dedup behavior
    without any real network access. Simulates the partial unique
    index on event_key: a POST whose event_key already exists on a
    stored row is rejected with HTTP 409, mirroring Postgres's
    unique_violation behavior via PostgREST, instead of being
    inserted.
    """

    def __init__(self, existing_rows=None):
        self.rows = list(existing_rows or [])
        self.get_calls = []
        self.post_calls = []
        self._next_id = len(self.rows) + 1

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

        if "brand" in params:
            value = params["brand"].removeprefix(
                "eq."
            )
            matches = [
                row
                for row in matches
                if row.get("brand") == value
            ]

        return FakeResponse(
            [
                {"id": row["id"]}
                for row in matches
            ]
        )

    def post(self, url, headers, json, timeout=None):
        event_key = json.get("event_key")

        if event_key is not None and any(
            row.get("event_key") == event_key
            for row in self.rows
        ):
            # Simulates the partial unique index rejecting a
            # concurrent/near-concurrent duplicate insert.
            return FakeResponse(
                {
                    "code": "23505",
                    "message": (
                        "duplicate key value violates "
                        "unique constraint "
                        "\"opportunities_event_key_unique\""
                    ),
                },
                status_code=409,
            )

        row = dict(json)
        row["id"] = self._next_id
        self._next_id += 1
        self.rows.append(row)
        self.post_calls.append(row)
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


def make_scout(monkeypatch, fake_supabase):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SERVICE_KEY",
        "test-service-key",
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
    monkeypatch.setattr(
        atlas_scout_module.LearningEngine,
        "record",
        lambda self, item, analysis: None,
    )

    scout = AtlasScout()
    scout.category = "test"

    return scout


def make_item():
    return {
        "title": "Test Product",
        "brand": "TestBrand",
        "url": (
            "https://example.com/"
            "test-product"
        ),
    }


def test_save_opportunity_without_event_key_skips_existing_url(
    monkeypatch,
):
    item = make_item()

    fake_supabase = FakeSupabaseOpportunities(
        existing_rows=[
            {
                "id": 1,
                "official_url": item["url"],
                "brand": item["brand"],
                "item_name": item["title"],
            }
        ]
    )

    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    saved = scout.save_opportunity(item)

    assert saved is False
    assert fake_supabase.post_calls == []


def test_save_opportunity_without_event_key_inserts_when_new(
    monkeypatch,
):
    item = make_item()

    fake_supabase = FakeSupabaseOpportunities()

    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    saved = scout.save_opportunity(item)

    assert saved is True
    assert len(fake_supabase.post_calls) == 1
    assert (
        fake_supabase.post_calls[0][
            "official_url"
        ]
        == item["url"]
    )
    assert (
        fake_supabase.post_calls[0][
            "item_name"
        ]
        == item["title"]
    )
    assert (
        "event_key"
        not in fake_supabase.post_calls[0]
    )


def test_save_opportunity_default_signature_matches_prior_behavior(
    monkeypatch,
):
    """
    Non-Pokémon scouts (OnePieceScout, LorcanaScout, and any future
    scout extending AtlasScout) call save_opportunity(item) with no
    second argument at all. This must behave exactly as it did before
    event_key was introduced.
    """

    item = make_item()

    fake_supabase = FakeSupabaseOpportunities(
        existing_rows=[
            {
                "id": 1,
                "official_url": item["url"],
                "brand": item["brand"],
                "item_name": item["title"],
            }
        ]
    )

    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    saved = scout.save_opportunity(item)

    assert saved is False
    assert len(fake_supabase.get_calls) >= 1
    assert fake_supabase.post_calls == []


def test_save_opportunity_with_event_key_inserts_first_occurrence(
    monkeypatch,
):
    item = make_item()

    fake_supabase = FakeSupabaseOpportunities(
        existing_rows=[
            {
                "id": 1,
                "official_url": item["url"],
                "brand": item["brand"],
                "item_name": item["title"],
            }
        ]
    )

    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    saved = scout.save_opportunity(
        item,
        event_key="pokemon:sku:x:RESTOCK:alert-001",
    )

    assert saved is True
    assert len(fake_supabase.post_calls) == 1
    assert (
        fake_supabase.post_calls[0][
            "event_key"
        ]
        == "pokemon:sku:x:RESTOCK:alert-001"
    )


def test_save_opportunity_with_event_key_returns_false_for_exact_repeat(
    monkeypatch,
):
    item = make_item()

    fake_supabase = FakeSupabaseOpportunities()
    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    first = scout.save_opportunity(
        item,
        event_key="pokemon:sku:x:RESTOCK:alert-001",
    )

    second = scout.save_opportunity(
        item,
        event_key="pokemon:sku:x:RESTOCK:alert-001",
    )

    assert first is True
    assert second is False
    assert len(fake_supabase.post_calls) == 1
    assert len(fake_supabase.rows) == 1


def test_save_opportunity_with_event_key_allows_a_later_distinct_event(
    monkeypatch,
):
    item = make_item()

    fake_supabase = FakeSupabaseOpportunities()
    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    first = scout.save_opportunity(
        item,
        event_key="pokemon:sku:x:NEW_PRODUCT:alert-001",
    )

    second = scout.save_opportunity(
        item,
        event_key="pokemon:sku:x:RESTOCK:alert-002",
    )

    assert first is True
    assert second is True
    assert len(fake_supabase.rows) == 2

    # Same official_url/item_name on both rows - proving the
    # customer-facing fields were never touched to force uniqueness.
    urls = {
        row["official_url"]
        for row in fake_supabase.rows
    }
    assert urls == {item["url"]}


def test_save_opportunity_with_event_key_does_not_corrupt_official_url(
    monkeypatch,
):
    item = make_item()

    fake_supabase = FakeSupabaseOpportunities()
    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    scout.save_opportunity(
        item,
        event_key="pokemon:sku:x:RESTOCK:alert-002",
    )

    posted = fake_supabase.post_calls[0]

    assert posted["official_url"] == item["url"]
    assert posted["item_name"] == item["title"]


def test_concurrent_insert_race_on_same_event_key_is_rejected_by_the_unique_index(
    monkeypatch,
):
    """
    Simulates two near-concurrent processes both passing the
    pre-check GET (neither sees the other's row yet) and both
    attempting the POST. The fake's unique-index simulation ensures
    only one insert can ever succeed for the same event_key,
    regardless of GET-check timing.
    """

    item = make_item()

    fake_supabase = FakeSupabaseOpportunities()
    scout_a = make_scout(monkeypatch, fake_supabase)
    scout_a.brand = item["brand"]

    scout_b = make_scout(monkeypatch, fake_supabase)
    scout_b.brand = item["brand"]

    event_key = "pokemon:sku:x:RESTOCK:alert-race"

    # Both "processes" skip their own GET pre-check by calling the
    # POST path directly, mirroring a true race where both already
    # observed no existing row before either wrote.
    response_a = fake_supabase.post(
        url="",
        headers={},
        json={
            "official_url": item["url"],
            "item_name": item["title"],
            "event_key": event_key,
        },
    )
    response_b = fake_supabase.post(
        url="",
        headers={},
        json={
            "official_url": item["url"],
            "item_name": item["title"],
            "event_key": event_key,
        },
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 409
    assert len(fake_supabase.rows) == 1


def test_event_key_exists_reflects_stored_rows(
    monkeypatch,
):
    fake_supabase = FakeSupabaseOpportunities(
        existing_rows=[
            {
                "id": 1,
                "event_key": (
                    "pokemon:sku:x:RESTOCK:alert-001"
                ),
            }
        ]
    )

    scout = make_scout(monkeypatch, fake_supabase)

    assert (
        scout.event_key_exists(
            "pokemon:sku:x:RESTOCK:alert-001"
        )
        is True
    )
    assert (
        scout.event_key_exists(
            "pokemon:sku:x:RESTOCK:alert-999"
        )
        is False
    )


def test_legacy_rows_without_event_key_remain_valid(
    monkeypatch,
):
    """
    Rows written before event_key existed simply have no event_key
    at all. They must not interfere with event_key lookups and must
    still be found by the original official_url/item_name check.
    """

    item = make_item()

    fake_supabase = FakeSupabaseOpportunities(
        existing_rows=[
            {
                "id": 1,
                "official_url": item["url"],
                "brand": item["brand"],
                "item_name": item["title"],
                # no "event_key" key at all
            }
        ]
    )

    scout = make_scout(monkeypatch, fake_supabase)
    scout.brand = item["brand"]

    assert (
        scout.event_key_exists(
            "pokemon:sku:x:RESTOCK:alert-001"
        )
        is False
    )
    assert scout.opportunity_exists(item) is True

    # A genuinely new event for this legacy-known product must still
    # be allowed through via event_key.
    saved = scout.save_opportunity(
        item,
        event_key="pokemon:sku:x:RESTOCK:alert-001",
    )
    assert saved is True


def make_non_pokemon_scout(monkeypatch, scout_class, fake_supabase):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SERVICE_KEY",
        "test-service-key",
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
    monkeypatch.setattr(
        atlas_scout_module.LearningEngine,
        "record",
        lambda self, item, analysis: None,
    )

    return scout_class()


def test_one_piece_scout_save_opportunity_call_site_is_unchanged(
    monkeypatch,
):
    """
    OnePieceScout.run() calls self.save_opportunity(item) with no
    second argument, exactly as it did before event_key existed
    (scouts/one_piece/collector.py:201-205). This proves that call
    site still produces the exact old URL/title dedup behavior.
    """

    item = {
        "title": "One Piece Booster Box",
        "brand": "One Piece Card Game",
        "url": (
            "https://example.com/"
            "one-piece-booster-box"
        ),
    }

    fake_supabase = FakeSupabaseOpportunities(
        existing_rows=[
            {
                "id": 1,
                "official_url": item["url"],
                "brand": item["brand"],
                "item_name": item["title"],
            }
        ]
    )

    scout = make_non_pokemon_scout(
        monkeypatch,
        OnePieceScout,
        fake_supabase,
    )

    duplicate = scout.save_opportunity(item)
    assert duplicate is False
    assert fake_supabase.post_calls == []

    # opportunity_exists() checks official_url OR brand+item_name, so
    # both must differ from the seeded row for this to be a genuinely
    # distinct, non-duplicate product.
    new_item = {
        **item,
        "url": item["url"] + "-v2",
        "title": item["title"] + " V2",
    }
    inserted = scout.save_opportunity(new_item)
    assert inserted is True
    assert len(fake_supabase.post_calls) == 1
    assert (
        "event_key"
        not in fake_supabase.post_calls[0]
    )


def test_lorcana_scout_save_opportunity_call_site_is_unchanged(
    monkeypatch,
):
    """
    LorcanaScout.run() calls self.save_opportunity(item) with no
    second argument, exactly as it did before event_key existed
    (scouts/lorcana/collector.py:194-198).
    """

    item = {
        "title": "Lorcana Rise of the Floodborn Booster",
        "brand": "Disney Lorcana",
        "url": (
            "https://example.com/"
            "lorcana-rotf-booster"
        ),
    }

    fake_supabase = FakeSupabaseOpportunities(
        existing_rows=[
            {
                "id": 1,
                "official_url": item["url"],
                "brand": item["brand"],
                "item_name": item["title"],
            }
        ]
    )

    scout = make_non_pokemon_scout(
        monkeypatch,
        LorcanaScout,
        fake_supabase,
    )

    duplicate = scout.save_opportunity(item)
    assert duplicate is False
    assert fake_supabase.post_calls == []

    # opportunity_exists() checks official_url OR brand+item_name, so
    # both must differ from the seeded row for this to be a genuinely
    # distinct, non-duplicate product.
    new_item = {
        **item,
        "url": item["url"] + "-v2",
        "title": item["title"] + " V2",
    }
    inserted = scout.save_opportunity(new_item)
    assert inserted is True
    assert len(fake_supabase.post_calls) == 1
    assert (
        "event_key"
        not in fake_supabase.post_calls[0]
    )
