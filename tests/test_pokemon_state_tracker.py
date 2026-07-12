from scouts.pokemon.state_tracker import (
    PokemonStateTracker,
)


def test_first_observation_is_new_product(
    tmp_path,
):
    tracker = PokemonStateTracker(
        path=(
            tmp_path
            / "pokemon_states.json"
        )
    )

    item = {
        "title": "Test Elite Trainer Box",
        "sku": "TEST-001",
        "retail_price": 59.99,
        "availability": "InStock",
        "sources": [
            "pokemon_center_tcg",
        ],
    }

    result = tracker.observe(item)

    assert (
        result["event"]
        == "NEW_PRODUCT"
    )
    assert (
        result["importance"]
        == "HIGH"
    )


def test_out_of_stock_to_in_stock_is_restock(
    tmp_path,
):
    tracker = PokemonStateTracker(
        path=(
            tmp_path
            / "pokemon_states.json"
        )
    )

    unavailable = {
        "title": "Test Booster Bundle",
        "sku": "TEST-002",
        "retail_price": 29.99,
        "availability": "OutOfStock",
    }

    available = {
        "title": "Test Booster Bundle",
        "sku": "TEST-002",
        "retail_price": 29.99,
        "availability": "InStock",
    }

    tracker.observe(unavailable)

    result = tracker.observe(available)

    assert result["event"] == "RESTOCK"
    assert (
        result["importance"]
        == "VERY HIGH"
    )


def test_price_drop_is_detected(
    tmp_path,
):
    tracker = PokemonStateTracker(
        path=(
            tmp_path
            / "pokemon_states.json"
        )
    )

    original = {
        "title": "Test Collection Box",
        "sku": "TEST-003",
        "retail_price": 49.99,
        "availability": "InStock",
    }

    discounted = {
        "title": "Test Collection Box",
        "sku": "TEST-003",
        "retail_price": 39.99,
        "availability": "InStock",
    }

    tracker.observe(original)

    result = tracker.observe(
        discounted
    )

    assert (
        result["event"]
        == "PRICE_DROP"
    )

    assert "$49.99" in result["reason"]
    assert "$39.99" in result["reason"]


def test_unchanged_item_returns_no_change(
    tmp_path,
):
    tracker = PokemonStateTracker(
        path=(
            tmp_path
            / "pokemon_states.json"
        )
    )

    item = {
        "title": "Test Pikachu Plush",
        "sku": "TEST-004",
        "retail_price": 34.99,
        "availability": "InStock",
    }

    tracker.observe(item)

    result = tracker.observe(item)

    assert (
        result["event"]
        == "NO_CHANGE"
    )