from scouts.pokemon.alert_store import (
    PokemonAlertStore,
)


def test_duplicate_active_alert_is_not_saved(
    tmp_path,
):
    store = PokemonAlertStore(
        path=(
            tmp_path
            / "alerts.json"
        )
    )

    item = {
        "title": "Test ETB",
        "sku": "TEST-500",
    }

    alert = {
        "event": "RESTOCK",
        "priority": "HIGH",
        "score": 80,
        "action": "CHECK AND BUY QUICKLY",
        "should_alert": True,
        "reasons": [],
    }

    first = store.save(
        item=item,
        alert=alert,
    )

    second = store.save(
        item=item,
        alert=alert,
    )

    assert first is not None
    assert second is None
    assert len(store.all()) == 1


def test_resolved_alert_can_be_created_again(
    tmp_path,
):
    store = PokemonAlertStore(
        path=(
            tmp_path
            / "alerts.json"
        )
    )

    item = {
        "title": "Test Booster Bundle",
        "sku": "TEST-501",
    }

    alert = {
        "event": "RESTOCK",
        "priority": "HIGH",
        "score": 80,
        "action": "CHECK AND BUY QUICKLY",
        "should_alert": True,
        "reasons": [],
    }

    first = store.save(
        item=item,
        alert=alert,
    )

    resolved = store.mark_resolved(
        first["alert_id"]
    )

    second = store.save(
        item=item,
        alert=alert,
    )

    assert resolved is True
    assert second is not None
    assert len(store.all()) == 2