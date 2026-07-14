LORCANA_SOURCES = [
    {
        "name": "lorcana_news",
        "url": (
            "https://www.disneylorcana.com/"
            "en-US/news"
        ),
        "base_url": (
            "https://www.disneylorcana.com"
        ),
        "allowed_paths": [
            "/en-US/news/",
            "/en-US/product/",
        ],
        "source_type": "news",
    },
    {
        "name": "lorcana_resources",
        "url": (
            "https://www.disneylorcana.com/"
            "en-US/resources"
        ),
        "base_url": (
            "https://www.disneylorcana.com"
        ),
        "allowed_paths": [
            "/en-US/product/",
            "/en-US/resources/",
        ],
        "source_type": "resources",
    },
    {
        "name": "lorcana_home",
        "url": (
            "https://www.disneylorcana.com/"
            "en-US/"
        ),
        "base_url": (
            "https://www.disneylorcana.com"
        ),
        "allowed_paths": [
            "/en-US/product/",
            "/en-US/news/",
        ],
        "source_type": "home",
    },
    {
        "name": "ravensburger_lorcana",
        "url": (
            "https://www.ravensburger.us/"
            "en-US/products/disney-lorcana"
        ),
        "base_url": (
            "https://www.ravensburger.us"
        ),
        "allowed_paths": [
            "/en-US/products/disney-lorcana",
            "/en-US/products/",
        ],
        "source_type": "products",
    },
]


OFFICIAL_LORCANA_HOSTS = {
    "disneylorcana.com",
    "www.disneylorcana.com",
    "ravensburger.us",
    "www.ravensburger.us",
}