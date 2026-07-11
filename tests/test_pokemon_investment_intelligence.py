from scouts.pokemon.investment_intelligence import (
    calculate_investment_intelligence,
)


def test_exclusive_etb_favors_hold_or_flip():
    item = {
        "product_type": "elite_trainer_box",
        "collector_score": 90,
        "popularity": {
            "score": 85,
        },
        "release_urgency": {
            "score": 90,
        },
        "pokemon_center_exclusive": True,
        "promo_included": True,
        "limited_release": True,
        "sealed_product": True,
        "availability": "SoldOut",
    }

    result = (
        calculate_investment_intelligence(
            item
        )
    )

    assert result["flip"]["score"] >= 70
    assert result["hold"]["score"] >= 70

    assert result[
        "best_strategy"
    ]["strategy"] in {
        "QUICK FLIP",
        "LONG-TERM HOLD",
    }


def test_low_hype_plush_can_be_a_sleeper():
    item = {
        "product_type": "plush",
        "collector_score": 60,
        "popularity": {
            "score": 20,
        },
        "release_urgency": {
            "score": 20,
        },
        "pokemon_center_exclusive": False,
        "promo_included": False,
        "limited_release": True,
        "sealed_product": False,
        "availability": "InStock",
    }

    result = (
        calculate_investment_intelligence(
            item
        )
    )

    assert (
        result["sleeper"]["score"]
        >= result["flip"]["score"]
    )

    assert (
        result["best_strategy"][
            "strategy"
        ]
        == "SLEEPER WATCH"
    )