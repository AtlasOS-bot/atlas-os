from scouts.pokemon.collector_intelligence import (
    calculate_collector_intelligence,
)


def test_exclusive_etb_gets_high_collector_score():
    item = {
        "product_type": "elite_trainer_box",
        "pokemon_center_exclusive": True,
        "promo_included": True,
        "limited_release": True,
        "sealed_product": True,
        "availability": "SoldOut",
        "release_urgency": {
            "score": 95,
        },
    }

    result = (
        calculate_collector_intelligence(
            item
        )
    )

    assert result["score"] >= 85
    assert result["level"] == "ELITE"
    assert (
        result["hold_profile"]
        == "STRONG LONG-TERM HOLD"
    )


def test_basic_accessory_gets_low_score():
    item = {
        "product_type": "accessory",
        "pokemon_center_exclusive": False,
        "promo_included": False,
        "limited_release": False,
        "sealed_product": False,
        "availability": "InStock",
        "release_urgency": {
            "score": 20,
        },
    }

    result = (
        calculate_collector_intelligence(
            item
        )
    )

    assert result["score"] < 35
    assert result["level"] == "LOW"