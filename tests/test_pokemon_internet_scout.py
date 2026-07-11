from scouts.pokemon.internet_scout import (
    deduplicate_items,
    extract_html_items,
)


def test_extracts_relevant_official_pokemon_items():
    html = """
    <html>
        <body>
            <a href="/us/pokemon-tcg/product-gallery/test-etb">
                Mega Evolution Test Elite Trainer Box
            </a>

            <a href="/us/privacy">
                Privacy
            </a>

            <a href="https://example.com/not-official">
                Limited Pokemon Product
            </a>
        </body>
    </html>
    """

    source = {
        "name": "test_source",
        "url": (
            "https://www.pokemon.com/"
            "us/pokemon-tcg/product-gallery"
        ),
        "base_url": "https://www.pokemon.com",
        "allowed_paths": [
            "/us/pokemon-tcg/product-gallery/",
        ],
    }

    items = extract_html_items(
        html=html,
        source=source,
    )

    assert len(items) == 1
    assert (
        items[0]["title"]
        == "Mega Evolution Test Elite Trainer Box"
    )
    assert items[0]["category"] == "pokemon"


def test_pokemon_items_are_deduplicated():
    items = [
        {
            "title": "Test Elite Trainer Box",
            "url": "https://example.com/test",
            "description": "Short",
        },
        {
            "title": "Test Elite Trainer Box",
            "url": "https://example.com/test",
            "description": (
                "Longer product description"
            ),
        },
    ]

    unique = deduplicate_items(items)

    assert len(unique) == 1
    assert (
        unique[0]["description"]
        == "Longer product description"
    )