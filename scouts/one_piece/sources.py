ONE_PIECE_SOURCES = [
    {
        "name": "one_piece_products",
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
    },
    {
        "name": "one_piece_topics",
        "url": (
            "https://en.onepiece-cardgame.com/"
            "topics/"
        ),
        "base_url": (
            "https://en.onepiece-cardgame.com"
        ),
        "allowed_paths": [
            "/topics/",
            "/products/",
        ],
        "source_type": "news",
    },
    {
        "name": "one_piece_home",
        "url": (
            "https://en.onepiece-cardgame.com/"
        ),
        "base_url": (
            "https://en.onepiece-cardgame.com"
        ),
        "allowed_paths": [
            "/products/",
            "/topics/",
        ],
        "source_type": "home",
    },
    {
        "name": "one_piece_card_list",
        "url": (
            "https://en.onepiece-cardgame.com/"
            "cardlist/"
        ),
        "base_url": (
            "https://en.onepiece-cardgame.com"
        ),
        "allowed_paths": [
            "/cardlist/",
            "/products/",
        ],
        "source_type": "cards",
    },
    {
        "name": "premium_bandai_one_piece",
        "url": (
            "https://p-bandai.com/us/"
            "brand/onepiececardgame"
        ),
        "base_url": (
            "https://p-bandai.com"
        ),
        "allowed_paths": [
            "/us/item/",
            "/us/brand/onepiececardgame",
        ],
        "source_type": "premium_bandai",
    },
]


OFFICIAL_ONE_PIECE_HOSTS = {
    "en.onepiece-cardgame.com",
    "onepiece-cardgame.com",
    "www.onepiece-cardgame.com",
    "p-bandai.com",
    "www.p-bandai.com",
}