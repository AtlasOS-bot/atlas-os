from scouts.pokemon.alert_intelligence import (
    calculate_alert_intelligence,
)


def test_high_value_restock_creates_high_alert():
    item = {
        "state_change": {
            "event": "RESTOCK",
        },
        "popularity_score": 85,
        "collector_score": 88,
        "consensus_score": 75,
        "flip_score": 90,
        "hold_score": 80,
        "sleeper_score": 40,
    }

    result = (
        calculate_alert_intelligence(
            item
        )
    )

    assert result["should_alert"] is True
    assert result["score"] >= 70
    assert result["priority"] in {
        "HIGH",
        "CRITICAL",
    }
    assert (
        result["action"]
        == "CHECK AND BUY QUICKLY"
    )


def test_no_change_does_not_create_alert():
    item = {
        "state_change": {
            "event": "NO_CHANGE",
        },
        "popularity_score": 90,
        "collector_score": 90,
        "consensus_score": 90,
        "flip_score": 90,
        "hold_score": 90,
        "sleeper_score": 90,
    }

    result = (
        calculate_alert_intelligence(
            item
        )
    )

    assert result["should_alert"] is False
    assert result["event"] == "NO_CHANGE"