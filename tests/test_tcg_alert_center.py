from scouts.tcg.alert_intelligence import (
    analyze_tcg_alert,
)
from scouts.tcg.alert_store import (
    TcgAlertStore,
)


def test_high_value_restock_is_high_alert():
    item = {
        "opportunity_score": 88,
        "opportunity_tier": (
            "CRITICAL"
        ),
        "collector_score": 90,
        "popularity_score": 85,
        "flip_score": 92,
        "hold_score": 80,
        "best_strategy": {
            "strategy": (
                "QUICK FLIP"
            ),
            "score": 92,
        },
    }

    change = {
        "event": "RESTOCK",
        "reason": (
            "Product returned to stock."
        ),
    }

    alert = analyze_tcg_alert(
        item=item,
        change=change,
    )

    assert alert[
        "should_alert"
    ] is True

    assert alert["priority"] in {
        "HIGH",
        "CRITICAL",
    }

    assert alert["score"] >= 70


def test_duplicate_active_alert_is_skipped(
    tmp_path,
):
    store = TcgAlertStore(
        path=(
            tmp_path
            / "alerts.json"
        )
    )

    item = {
        "title": "Test Product",
        "category": "one_piece",
        "flip_score": 80,
        "hold_score": 70,
        "best_strategy": {
            "strategy": (
                "QUICK FLIP"
            ),
            "score": 80,
        },
    }

    alert = {
        "event": "RESTOCK",
        "priority": "HIGH",
        "score": 80,
        "action": (
            "CHECK STOCK"
        ),
        "reason": (
            "Restock detected."
        ),
        "reasons": [],
        "should_alert": True,
    }

    first = store.save(
        item=item,
        product_key=(
            "one_piece:sku:test"
        ),
        alert=alert,
    )

    second = store.save(
        item=item,
        product_key=(
            "one_piece:sku:test"
        ),
        alert=alert,
    )

    assert first is not None
    assert second is None
    assert len(store.all()) == 1