from datetime import datetime, timedelta, timezone

from scouts.pokemon.alert_intelligence import (
    calculate_alert_intelligence,
)
from scouts.pokemon.alert_store import (
    PokemonAlertStore,
)
from scouts.pokemon.enrichment import (
    enrich_pokemon_item,
)
from scouts.pokemon.parser import (
    parse_pokemon_item,
)
from scouts.pokemon.state_tracker import (
    PokemonStateTracker,
)


def build_pokemon_center_etb_item(availability):
    release_date = (
        datetime.now(timezone.utc).date()
        + timedelta(days=3)
    ).isoformat()

    raw_item = parse_pokemon_item(
        title=(
            "Pokémon Center Exclusive Elite Trainer Box "
            "- Mega Dragonite ex"
        ),
        url=(
            "https://www.pokemoncenter.com/product/"
            "12345-mega-dragonite-ex-elite-trainer-box"
        ),
        description=(
            "This Pokémon Center Exclusive Elite Trainer Box "
            "includes an exclusive stamped promo card and is a "
            "limited release ahead of general availability."
        ),
    )

    raw_item["sku"] = "PC-ETB-DRAGONITE-EX"
    raw_item["retail_price"] = 59.99
    raw_item["availability"] = availability
    raw_item["release_date"] = release_date
    raw_item["sources"] = [
        "pokemon_center_tcg",
        "pokemon_center",
    ]

    return enrich_pokemon_item(raw_item)


def observe_and_score(tracker, item):
    state_change = tracker.observe(item)

    item["state_change"] = state_change
    item["state_event"] = state_change["event"]
    item["state_importance"] = state_change["importance"]

    alert = calculate_alert_intelligence(item)

    return state_change, alert


def test_new_product_scan_creates_alert(tmp_path):
    tracker = PokemonStateTracker(
        path=tmp_path / "pokemon_states.json"
    )

    store = PokemonAlertStore(
        path=tmp_path / "pokemon_alerts.json"
    )

    item = build_pokemon_center_etb_item("InStock")

    state_change, alert = observe_and_score(
        tracker,
        item,
    )

    assert state_change["event"] == "NEW_PRODUCT"
    assert state_change["importance"] == "HIGH"

    assert alert["event"] == "NEW_PRODUCT"
    assert alert["should_alert"] is True
    assert alert["score"] >= 30
    assert alert["priority"] in {
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }

    saved = store.save(
        item=item,
        alert=alert,
    )

    assert saved is not None
    assert len(store.all()) == 1
    assert store.all()[0]["event"] == "NEW_PRODUCT"


def test_duplicate_scan_does_not_duplicate_new_product_alert(
    tmp_path,
):
    tracker = PokemonStateTracker(
        path=tmp_path / "pokemon_states.json"
    )

    store = PokemonAlertStore(
        path=tmp_path / "pokemon_alerts.json"
    )

    first_item = build_pokemon_center_etb_item("InStock")

    first_state_change, first_alert = observe_and_score(
        tracker,
        first_item,
    )

    assert first_state_change["event"] == "NEW_PRODUCT"

    store.save(
        item=first_item,
        alert=first_alert,
    )

    duplicate_item = build_pokemon_center_etb_item("InStock")

    duplicate_state_change, duplicate_alert = observe_and_score(
        tracker,
        duplicate_item,
    )

    assert duplicate_state_change["event"] == "NO_CHANGE"
    assert duplicate_alert["should_alert"] is False

    duplicate_saved = store.save(
        item=duplicate_item,
        alert=duplicate_alert,
    )

    assert duplicate_saved is None
    assert len(store.all()) == 1


def test_sold_out_then_restock_sequence_produces_distinct_events(
    tmp_path,
):
    tracker = PokemonStateTracker(
        path=tmp_path / "pokemon_states.json"
    )

    store = PokemonAlertStore(
        path=tmp_path / "pokemon_alerts.json"
    )

    new_product_item = build_pokemon_center_etb_item("InStock")

    new_product_state, new_product_alert = observe_and_score(
        tracker,
        new_product_item,
    )

    assert new_product_state["event"] == "NEW_PRODUCT"
    assert new_product_state["importance"] == "HIGH"

    store.save(
        item=new_product_item,
        alert=new_product_alert,
    )

    sold_out_item = build_pokemon_center_etb_item("OutOfStock")

    sold_out_state, sold_out_alert = observe_and_score(
        tracker,
        sold_out_item,
    )

    assert sold_out_state["event"] == "SOLD_OUT"
    assert sold_out_state["importance"] == "HIGH"

    store.save(
        item=sold_out_item,
        alert=sold_out_alert,
    )

    restock_item = build_pokemon_center_etb_item("InStock")

    restock_state, restock_alert = observe_and_score(
        tracker,
        restock_item,
    )

    assert restock_state["event"] == "RESTOCK"
    assert restock_state["importance"] == "VERY HIGH"

    store.save(
        item=restock_item,
        alert=restock_alert,
    )

    records = store.all()

    assert len(records) == 3

    events = {record["event"] for record in records}
    assert events == {
        "NEW_PRODUCT",
        "SOLD_OUT",
        "RESTOCK",
    }

    product_keys = {
        record["product_key"] for record in records
    }
    assert len(product_keys) == 1
