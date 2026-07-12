from scouts.pokemon.product_details import (
    extract_product_details,
)


def test_extracts_pack_and_promo_counts():
    item = {
        "title": (
            "Pokémon Elite Trainer Box"
        ),
        "description": (
            "Includes 9 Pokémon TCG "
            "booster packs, 1 promo card, "
            "card sleeves, dice, and dividers."
        ),
        "product_type": (
            "elite_trainer_box"
        ),
        "retail_price": 59.99,
        "currency": "USD",
        "release_date": "2026-08-01",
        "availability": "InStock",
        "sku": "TEST-900",
        "image_url": (
            "https://example.com/image.jpg"
        ),
    }

    details = extract_product_details(
        item
    )

    assert details["pack_count"] == 9

    assert (
        details["promo_card_count"]
        == 1
    )

    assert (
        "Card sleeves"
        in details[
            "included_accessories"
        ]
    )

    assert (
        details[
            "detail_completeness_score"
        ]
        >= 80
    )


def test_missing_information_is_reported():
    item = {
        "title": "Pikachu Plush",
        "description": "",
        "product_type": "plush",
    }

    details = extract_product_details(
        item
    )

    assert (
        details[
            "detail_completeness_level"
        ]
        == "LIMITED"
    )

    assert (
        "retail_price"
        in details[
            "missing_detail_fields"
        ]
    )