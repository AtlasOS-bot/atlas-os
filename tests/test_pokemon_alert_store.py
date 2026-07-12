from scouts.pokemon.alert_store import (
    PokemonAlertStore,
)


def test_alert_store_saves_important_alert(
    tmp_path,
):
    store = PokemonAlertStore(
        path=(
            tmp_path
            / "pokemon_alerts.json"
        )
    )

    item = {
        "title": "Test Booster Bundle",
        "url": "https://example.com/test",
        "sku": "TEST-100",
        "product_type": "booster_bundle",
        "state_change": {
            "reason": (
                "The item returned to stock."
            ),
        },
        "best_strategy": {
            "strategy": "QUICK FLIP",
        },
        "flip_score": 85,
        "hold_score": 60,
        "sleeper_score": 30,
        "collector_score": 75,
        "popularity_score": 80,
    }

    alert = {
        "event": "RESTOCK",
        "priority": "HIGH",
        "score": 82,
        "action": "CHECK AND BUY QUICKLY",
        "should_alert": True,
        "reasons": [
            "Restock detected.",
        ],
    }

    record = store.save(
        item=item,
        alert=alert,
    )

    records = store.all()

    assert record is not None
    assert len(records) == 1
    assert records[0]["event"] == "RESTOCK"
    assert records[0]["priority"] == "HIGH"


def test_alert_store_ignores_unimportant_event(
    tmp_path,
):
    store = PokemonAlertStore(
        path=(
            tmp_path
            / "pokemon_alerts.json"
        )
    )

    record = store.save(
        item={
            "title": "Unchanged Item",
        },
        alert={
            "event": "NO_CHANGE",
            "should_alert": False,
        },
    )

    assert record is None
    assert store.all() == []