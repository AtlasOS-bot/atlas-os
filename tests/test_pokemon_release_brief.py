from datetime import date

from scouts.pokemon.release_brief import (
    PokemonReleaseBrief,
)


def test_release_brief_contains_action():
    items = [
        {
            "title": "Release Day Product",
            "release_date": (
                date(
                    2026,
                    7,
                    11,
                ).isoformat()
            ),
            "product_type": (
                "elite_trainer_box"
            ),
        }
    ]

    brief = PokemonReleaseBrief.generate(
        items=items,
        today=date(
            2026,
            7,
            11,
        ),
    )

    assert (
        "ATLAS POKÉMON RELEASE CALENDAR"
        in brief
    )

    assert "RELEASE DAY" in brief

    assert (
        "CHECK STOCK IMMEDIATELY"
        in brief
    )