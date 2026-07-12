from datetime import date

from scouts.pokemon.release_store import (
    PokemonReleaseStore,
)


def test_release_store_saves_calendar(
    tmp_path,
):
    path = (
        tmp_path
        / "release_calendar.json"
    )

    store = PokemonReleaseStore(
        path=path
    )

    items = [
        {
            "title": "Test Product",
            "release_date": (
                date(
                    2026,
                    7,
                    20,
                ).isoformat()
            ),
            "product_type": (
                "elite_trainer_box"
            ),
        }
    ]

    payload = store.save(
        items=items,
        today=date(
            2026,
            7,
            11,
        ),
    )

    loaded = store.load()

    assert payload["count"] == 1
    assert loaded["count"] == 1

    assert (
        loaded["releases"][0][
            "title"
        ]
        == "Test Product"
    )