from scouts.pokemon.consensus import (
    build_consensus,
)


def test_same_product_sources_are_combined():
    items = [
        {
            "title": (
                "Mega Evolution Ascended "
                "Heroes Booster Bundle"
            ),
            "url": (
                "https://pokemon.com/product-a"
            ),
            "source": "pokemon_news",
            "sources": [
                "pokemon_news",
            ],
            "description": "Short description",
        },
        {
            "title": (
                "Pokémon TCG Mega Evolution "
                "Ascended Heroes Booster Bundle"
            ),
            "url": (
                "https://pokemoncenter.com/product-b"
            ),
            "source": (
                "pokemon_center_tcg"
            ),
            "sources": [
                "pokemon_center_tcg",
            ],
            "description": (
                "Longer structured product "
                "description"
            ),
            "retail_price": 29.99,
        },
    ]

    result = build_consensus(
        items
    )

    assert len(result) == 1

    product = result[0]

    assert (
        product["confirmation_count"]
        == 2
    )

    assert set(product["sources"]) == {
        "pokemon_news",
        "pokemon_center_tcg",
    }

    assert product["retail_price"] == 29.99
    assert product["consensus_score"] >= 50