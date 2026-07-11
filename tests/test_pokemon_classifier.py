from datetime import date, timedelta

from scouts.pokemon.classifier import (
    calculate_release_urgency,
    classify_pokemon_product,
)


def test_classifies_pokemon_center_etb():
    item = {
        "title": (
            "Pokémon Center Exclusive "
            "Elite Trainer Box"
        ),
        "description": (
            "Includes an exclusive promo card"
        ),
    }

    result = classify_pokemon_product(
        item
    )

    assert (
        result["product_type"]
        == "elite_trainer_box"
    )
    assert result["sealed_product"] is True
    assert (
        result["pokemon_center_exclusive"]
        is True
    )
    assert result["promo_included"] is True
    assert (
        result["collector_tier"]
        == "VERY HIGH"
    )


def test_classifies_pokemon_plush():
    item = {
        "title": "Pikachu Poké Plush",
        "description": "",
    }

    result = classify_pokemon_product(
        item
    )

    assert result["product_type"] == "plush"
    assert result["sealed_product"] is False


def test_upcoming_release_has_high_urgency():
    today = date(2026, 7, 11)

    item = {
        "release_date": (
            today + timedelta(days=5)
        ).isoformat(),
    }

    result = calculate_release_urgency(
        item=item,
        today=today,
    )

    assert result["level"] == "VERY HIGH"
    assert result["score"] == 90