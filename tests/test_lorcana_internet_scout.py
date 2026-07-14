from scouts.lorcana.internet_scout import (
    deduplicate_lorcana_items,
    extract_html_items,
    extract_structured_items,
)


TEST_SOURCE = {
    "name": "lorcana_test",
    "url": (
        "https://www.disneylorcana.com/"
        "en-US/resources"
    ),
    "base_url": (
        "https://www.disneylorcana.com"
    ),
    "allowed_paths": [
        "/en-US/product/",
    ],
    "source_type": "resources",
}


def test_extracts_official_lorcana_link():
    html = """
    <html>
        <body>
            <a href="/en-US/product/test-gift-set">
                Disney Lorcana Limited Gift Set
            </a>

            <a href="/en-US/privacy">
                Privacy
            </a>

            <a href="https://example.com/fake-product">
                Disney Lorcana Booster Box
            </a>
        </body>
    </html>
    """

    items = extract_html_items(
        html=html,
        source=TEST_SOURCE,
    )

    assert len(items) == 1

    assert (
        items[0]["title"]
        == "Disney Lorcana Limited Gift Set"
    )

    assert (
        items[0]["source"]
        == "lorcana_test"
    )


def test_extracts_structured_lorcana_product():
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Disney Lorcana Collector Gift Set",
                "description":
                    "Limited gift set with promo cards.",
                "url": "/en-US/product/collector-gift-set",
                "sku": "LOR-100",
                "image": "/images/gift-set.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": "49.99",
                    "priceCurrency": "USD",
                    "availability":
                        "https://schema.org/InStock"
                }
            }
            </script>
        </head>
    </html>
    """

    items = extract_structured_items(
        html=html,
        source=TEST_SOURCE,
    )

    assert len(items) == 1

    product = items[0]

    assert (
        product["retail_price"]
        == 49.99
    )

    assert (
        product["currency"]
        == "USD"
    )

    assert (
        product["availability"]
        == "InStock"
    )

    assert product["sku"] == "LOR-100"


def test_lorcana_items_are_deduplicated():
    items = [
        {
            "title": (
                "Disney Lorcana Gift Set"
            ),
            "url": (
                "https://www.disneylorcana.com/"
                "en-US/product/gift-set"
            ),
            "description": "Short",
            "source": "lorcana_news",
            "sources": [
                "lorcana_news",
            ],
        },
        {
            "title": (
                "Disney Lorcana Gift Set"
            ),
            "url": (
                "https://www.disneylorcana.com/"
                "en-US/product/gift-set"
            ),
            "description": (
                "Longer official product "
                "description."
            ),
            "source": (
                "lorcana_resources"
            ),
            "sources": [
                "lorcana_resources",
            ],
        },
    ]

    result = (
        deduplicate_lorcana_items(
            items
        )
    )

    assert len(result) == 1

    assert set(
        result[0]["sources"]
    ) == {
        "lorcana_news",
        "lorcana_resources",
    }

    assert (
        result[0]["description"]
        == (
            "Longer official product "
            "description."
        )
    )