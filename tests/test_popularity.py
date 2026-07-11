from popularity.engine import PopularityEngine


def test_high_popularity_pokemon_item():
    item = {
        "title": (
            "Pokémon Center Exclusive "
            "Elite Trainer Box Promo Card"
        ),
        "description": (
            "Limited anniversary collector product"
        ),
        "category": "pokemon",
        "source": (
            "pokemon_center_new_releases"
        ),
        "sources": [
            "pokemon_center_new_releases",
            "pokemon_news",
            "pokemon_tcg_gallery",
        ],
        "availability": "SoldOut",
    }

    result = PopularityEngine.analyze(
        item=item,
        category="pokemon",
    )

    assert result["score"] >= 85
    assert result["level"] == "VIRAL"
    assert result["confidence"] in {
        "HIGH",
        "VERY HIGH",
    }


def test_low_popularity_unknown_item():
    item = {
        "title": "Ordinary Product",
        "description": "",
        "category": "pokemon",
    }

    result = PopularityEngine.analyze(
        item=item,
        category="pokemon",
    )

    assert result["score"] <= 15
    assert result["level"] == "LOW"