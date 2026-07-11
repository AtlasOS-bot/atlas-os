from datetime import date, datetime, timezone


PRODUCT_RULES = [
    (
        "elite_trainer_box",
        [
            "elite trainer box",
            " etb",
            "etb ",
        ],
    ),
    (
        "booster_box",
        [
            "booster box",
            "display box",
        ],
    ),
    (
        "booster_bundle",
        [
            "booster bundle",
        ],
    ),
    (
        "collection_box",
        [
            "premium collection",
            "special collection",
            "ex collection",
            "collection box",
            "poster collection",
            "binder collection",
        ],
    ),
    (
        "tin",
        [
            " tin",
            "tin ",
            "mini tin",
        ],
    ),
    (
        "single_card",
        [
            "single card",
            "promo card",
        ],
    ),
    (
        "plush",
        [
            "plush",
            "poké plush",
        ],
    ),
    (
        "figure",
        [
            "figure",
            "figurine",
            "statue",
        ],
    ),
    (
        "pin",
        [
            "pin collection",
            "collector pin",
            "enamel pin",
        ],
    ),
    (
        "accessory",
        [
            "playmat",
            "card sleeves",
            "deck box",
            "binder",
            "backpack",
            "hat",
            "shirt",
            "hoodie",
        ],
    ),
]


SEALED_PRODUCT_TYPES = {
    "elite_trainer_box",
    "booster_box",
    "booster_bundle",
    "collection_box",
    "tin",
}


PRODUCT_TIER = {
    "booster_box": "VERY HIGH",
    "elite_trainer_box": "VERY HIGH",
    "booster_bundle": "HIGH",
    "collection_box": "HIGH",
    "single_card": "HIGH",
    "tin": "MEDIUM",
    "plush": "MEDIUM",
    "figure": "MEDIUM",
    "pin": "LOW",
    "accessory": "LOW",
    "other": "LOW",
}


def classify_pokemon_product(item):
    text = (
        f"{item.get('title', '')} "
        f"{item.get('description', '')}"
    ).lower()

    product_type = "other"

    for candidate_type, terms in PRODUCT_RULES:
        if any(term in text for term in terms):
            product_type = candidate_type
            break

    pokemon_center_exclusive = any(
        term in text
        for term in [
            "pokemon center exclusive",
            "pokémon center exclusive",
            "pokemon center edition",
            "pokémon center edition",
        ]
    )

    promo_included = any(
        term in text
        for term in [
            "promo card",
            "promo cards",
            "exclusive promo",
            "stamped promo",
        ]
    )

    limited_release = any(
        term in text
        for term in [
            "limited",
            "exclusive",
            "anniversary",
            "special release",
        ]
    )

    return {
        "product_type": product_type,
        "sealed_product": (
            product_type in SEALED_PRODUCT_TYPES
        ),
        "pokemon_center_exclusive": (
            pokemon_center_exclusive
        ),
        "promo_included": promo_included,
        "limited_release": limited_release,
        "collector_tier": PRODUCT_TIER.get(
            product_type,
            "LOW",
        ),
    }


def calculate_release_urgency(
    item,
    today=None,
):
    today = today or datetime.now(
        timezone.utc
    ).date()

    availability = (
        item.get("availability")
        or ""
    ).lower()

    if availability in {
        "soldout",
        "outofstock",
    }:
        return {
            "level": "VERY HIGH",
            "score": 95,
            "reason": (
                "Official product data indicates the item "
                "is sold out or out of stock."
            ),
        }

    release_date = parse_release_date(
        item.get("release_date")
    )

    if release_date:
        days_difference = (
            release_date - today
        ).days

        if 0 <= days_difference <= 7:
            return {
                "level": "VERY HIGH",
                "score": 90,
                "reason": (
                    f"The product releases in "
                    f"{days_difference} day(s)."
                ),
            }

        if 8 <= days_difference <= 21:
            return {
                "level": "HIGH",
                "score": 75,
                "reason": (
                    f"The product releases in "
                    f"{days_difference} day(s)."
                ),
            }

        if -3 <= days_difference < 0:
            return {
                "level": "HIGH",
                "score": 80,
                "reason": (
                    "The product was released within "
                    "the past three days."
                ),
            }

        if -14 <= days_difference < -3:
            return {
                "level": "MEDIUM",
                "score": 55,
                "reason": (
                    "The product was released within "
                    "the past two weeks."
                ),
            }

    if availability == "instock":
        return {
            "level": "MEDIUM",
            "score": 45,
            "reason": (
                "The product currently appears to be in stock."
            ),
        }

    return {
        "level": "LOW",
        "score": 20,
        "reason": (
            "Atlas has not detected an immediate "
            "release or availability deadline."
        ),
    }


def parse_release_date(value):
    if not value:
        return None

    if isinstance(value, date):
        return value

    text = str(value).strip()

    for candidate in [
        text,
        text[:10],
    ]:
        try:
            return datetime.fromisoformat(
                candidate.replace(
                    "Z",
                    "+00:00",
                )
            ).date()

        except ValueError:
            continue

    return None