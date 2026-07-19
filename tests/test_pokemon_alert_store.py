import json

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


def test_new_alert_record_defaults_to_not_forwarded(
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
            "title": "Test ETB",
            "sku": "TEST-200",
        },
        alert={
            "event": "RESTOCK",
            "priority": "HIGH",
            "score": 80,
            "action": "CHECK AND BUY QUICKLY",
            "should_alert": True,
            "reasons": [],
        },
    )

    assert record["opportunity_forwarded"] is False
    assert (
        store.is_opportunity_forwarded(
            record["alert_id"]
        )
        is False
    )


def test_mark_opportunity_forwarded_flips_only_the_matching_record(
    tmp_path,
):
    store = PokemonAlertStore(
        path=(
            tmp_path
            / "pokemon_alerts.json"
        )
    )

    record_a = store.save(
        item={
            "title": "Item A",
            "sku": "TEST-A",
        },
        alert={
            "event": "RESTOCK",
            "priority": "HIGH",
            "score": 80,
            "action": "CHECK AND BUY QUICKLY",
            "should_alert": True,
            "reasons": [],
        },
    )

    record_b = store.save(
        item={
            "title": "Item B",
            "sku": "TEST-B",
        },
        alert={
            "event": "RESTOCK",
            "priority": "HIGH",
            "score": 80,
            "action": "CHECK AND BUY QUICKLY",
            "should_alert": True,
            "reasons": [],
        },
    )

    updated = store.mark_opportunity_forwarded(
        record_a["alert_id"]
    )

    assert updated is True

    assert (
        store.is_opportunity_forwarded(
            record_a["alert_id"]
        )
        is True
    )

    assert (
        store.is_opportunity_forwarded(
            record_b["alert_id"]
        )
        is False
    )

    # Unrelated fields on record_b must be untouched.
    stored_b = next(
        record
        for record in store.all()
        if record["alert_id"]
        == record_b["alert_id"]
    )

    assert stored_b["title"] == "Item B"
    assert stored_b["status"] == "NEW"
    assert (
        stored_b["opportunity_forwarded"]
        is False
    )

    # The status field (resolution) must stay independent of forwarding.
    stored_a = next(
        record
        for record in store.all()
        if record["alert_id"]
        == record_a["alert_id"]
    )

    assert stored_a["status"] == "NEW"


def test_mark_opportunity_forwarded_returns_false_for_unknown_alert_id(
    tmp_path,
):
    store = PokemonAlertStore(
        path=(
            tmp_path
            / "pokemon_alerts.json"
        )
    )

    assert (
        store.mark_opportunity_forwarded(
            "does-not-exist"
        )
        is False
    )


def test_legacy_alert_records_without_forwarded_field_remain_readable(
    tmp_path,
):
    path = (
        tmp_path
        / "pokemon_alerts.json"
    )

    legacy_record = {
        "alert_id": "legacy-1",
        "product_key": "sku:legacy-100",
        "created_at": (
            "2026-01-01T00:00:00+00:00"
        ),
        "title": "Legacy ETB",
        "url": "https://example.com/legacy",
        "sku": "LEGACY-100",
        "event": "RESTOCK",
        "priority": "HIGH",
        "score": 80,
        "action": "CHECK AND BUY QUICKLY",
        "reasons": [],
        "status": "NEW",
        # Deliberately no "opportunity_forwarded" key,
        # simulating data written before this field existed.
    }

    path.write_text(
        json.dumps([legacy_record]),
        encoding="utf-8",
    )

    store = PokemonAlertStore(path=path)

    assert (
        store.is_opportunity_forwarded(
            "legacy-1"
        )
        is False
    )

    active = store.active_record_for(
        "sku:legacy-100"
    )

    assert active is not None
    assert active["alert_id"] == "legacy-1"

    updated = store.mark_opportunity_forwarded(
        "legacy-1"
    )

    assert updated is True

    assert (
        store.is_opportunity_forwarded(
            "legacy-1"
        )
        is True
    )

    # The historical fields must be unchanged aside from the new flag.
    stored = store.all()[0]

    assert stored["title"] == "Legacy ETB"
    assert stored["score"] == 80
    assert stored["status"] == "NEW"


def test_active_record_for_ignores_resolved_records(
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
            "title": "Test ETB",
            "sku": "TEST-300",
        },
        alert={
            "event": "RESTOCK",
            "priority": "HIGH",
            "score": 80,
            "action": "CHECK AND BUY QUICKLY",
            "should_alert": True,
            "reasons": [],
        },
    )

    store.mark_resolved(
        record["alert_id"]
    )

    assert (
        store.active_record_for(
            record["product_key"]
        )
        is None
    )