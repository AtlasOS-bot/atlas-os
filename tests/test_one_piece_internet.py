from scouts.one_piece.internet_scout import (
    deduplicate_one_piece_items,
    extract_one_piece_items,
)


TEST_SOURCE = {
    "name": "one_piece_test",
    "url": (
        "https://en.onepiece-cardgame.com/"
        "products/"
    ),
    "base_url": (
        "https://en.onepiece-cardgame.com"
    ),
    "allowed_paths": [
        "/products/",
    ],
    "source_type": "products",
}


def test_extracts_real_product_links_only():
    html = """
    <html>
        <body>
            <a href="/products/boosters/op15.php">
                BOOSTER PACK Adventure on
                Kami's Island OP-15
            </a>

            <a href="/products/decks/st29.php">
                STARTER DECK ST-29
            </a>

            <a href="/products/">
                View All Products
            </a>

            <a href="/faq/">
                FAQ
            </a>
        </body>
    </html>
    """

    items = extract_one_piece_items(
        html=html,
        source=TEST_SOURCE,
    )

    assert len(items) == 2

    titles = {
        item["title"]
        for item in items
    }

    assert (
        "STARTER DECK ST-29"
        in titles
    )

    assert any(
        "OP-15"
        in item["set_codes"]
        for item in items
    )


def test_one_piece_products_are_deduplicated():
    items = [
        {
            "title": (
                "STARTER DECK ST-29"
            ),
            "url": (
                "https://en.onepiece-cardgame.com/"
                "products/decks/st29.php"
            ),
            "description": "Short",
            "sources": [
                "one_piece_home",
            ],
            "set_codes": [
                "ST-29",
            ],
        },
        {
            "title": (
                "STARTER DECK ST-29"
            ),
            "url": (
                "https://en.onepiece-cardgame.com/"
                "products/decks/st29.php"
            ),
            "description": (
                "Long official product "
                "description."
            ),
            "sources": [
                "one_piece_products",
            ],
            "set_codes": [
                "ST-29",
            ],
        },
    ]

    result = (
        deduplicate_one_piece_items(
            items
        )
    )

    assert len(result) == 1

    assert set(
        result[0]["sources"]
    ) == {
        "one_piece_home",
        "one_piece_products",
    }

    assert (
        result[0]["description"]
        == (
            "Long official product "
            "description."
        )
    )