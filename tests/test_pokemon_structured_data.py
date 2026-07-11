from scouts.pokemon.structured_data import (
    extract_structured_candidates,
)


def test_extracts_json_ld_product():
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Pokémon Center Exclusive Pikachu Plush",
                "url": "/product/test-pikachu-plush",
                "description": "Limited collector plush",
                "sku": "TEST-001",
                "image": "/images/pikachu.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": "39.99",
                    "priceCurrency": "USD",
                    "availability":
                        "https://schema.org/InStock"
                }
            }
            </script>
        </head>
    </html>
    """

    source = {
        "name": "test_source",
        "url": (
            "https://www.pokemoncenter.com/"
            "category/new-releases"
        ),
        "base_url": (
            "https://www.pokemoncenter.com"
        ),
        "allowed_paths": [
            "/product/",
        ],
    }

    candidates = (
        extract_structured_candidates(
            html=html,
            source=source,
        )
    )

    assert len(candidates) == 1

    product = candidates[0]

    assert (
        product["title"]
        == "Pokémon Center Exclusive Pikachu Plush"
    )
    assert product["retail_price"] == 39.99
    assert product["currency"] == "USD"
    assert product["availability"] == "InStock"
    assert product["sku"] == "TEST-001"


def test_extracts_next_data_product():
    html = """
    <html>
        <body>
            <script id="__NEXT_DATA__"
                    type="application/json">
            {
                "props": {
                    "products": [
                        {
                            "@type": "Product",
                            "name":
                                "Pokémon Elite Trainer Box",
                            "url":
                                "/product/test-etb",
                            "offers": {
                                "price": 59.99,
                                "priceCurrency": "USD"
                            }
                        }
                    ]
                }
            }
            </script>
        </body>
    </html>
    """

    source = {
        "name": "test_source",
        "url": (
            "https://www.pokemoncenter.com/"
            "category/trading-card-game"
        ),
        "base_url": (
            "https://www.pokemoncenter.com"
        ),
        "allowed_paths": [
            "/product/",
        ],
    }

    candidates = (
        extract_structured_candidates(
            html=html,
            source=source,
        )
    )

    assert len(candidates) == 1
    assert candidates[0][
        "retail_price"
    ] == 59.99