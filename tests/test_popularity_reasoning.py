from brain.atlas_brain import AtlasBrain


def test_popularity_flows_into_reasoning():
    item = {
        "title": (
            "Pokémon Center Exclusive "
            "Elite Trainer Box"
        ),
        "description": (
            "Limited collector release "
            "with promo card"
        ),
        "brand": "Pokemon",
        "category": "pokemon",
        "url": "https://example.com/test-etb",
        "sources": [
            "pokemon_center_new_releases",
            "pokemon_news",
            "pokemon_tcg_gallery",
        ],
    }

    analysis = AtlasBrain.analyze(
        item=item,
        category="pokemon",
    )

    assert analysis["popularity"]["score"] >= 70

    evidence_types = [
        evidence["type"]
        for evidence in analysis["evidence"]
    ]

    assert "popularity" in evidence_types