from scouts.pokemon.alert_brief import (
    PokemonAlertBrief,
)


def test_alert_brief_places_high_priority_first():
    alerts = [
        {
            "title": "Low Product",
            "priority": "LOW",
            "score": 35,
            "event": "NEW_PRODUCT",
            "action": "ADD TO WATCHLIST",
        },
        {
            "title": "Critical Product",
            "priority": "CRITICAL",
            "score": 95,
            "event": "RESTOCK",
            "action": "CHECK AND BUY QUICKLY",
        },
    ]

    brief = PokemonAlertBrief.generate(
        alerts
    )

    assert (
        brief.index("Critical Product")
        < brief.index("Low Product")
    )

    assert (
        "ATLAS POKÉMON ALERT BRIEF"
        in brief
    )