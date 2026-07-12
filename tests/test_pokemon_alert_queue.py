from scouts.pokemon.alert_queue import (
    PokemonAlertQueue,
)


def test_critical_alert_ranks_first():
    alerts = [
        {
            "title": "Medium Alert",
            "priority": "MEDIUM",
            "score": 60,
            "flip_score": 90,
        },
        {
            "title": "Critical Alert",
            "priority": "CRITICAL",
            "score": 88,
            "flip_score": 70,
        },
        {
            "title": "High Alert",
            "priority": "HIGH",
            "score": 75,
            "flip_score": 95,
        },
    ]

    ranked = PokemonAlertQueue.rank(
        alerts
    )

    assert (
        ranked[0]["title"]
        == "Critical Alert"
    )

    assert (
        ranked[-1]["title"]
        == "Medium Alert"
    )