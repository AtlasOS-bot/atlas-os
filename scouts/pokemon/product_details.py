import re


PACK_PATTERNS = [
    (
        r"includes?\s+(\d+)\s+"
        r"(?:pok[eé]mon\s+tcg\s+)?"
        r"booster packs?"
    ),
    (
        r"contains?\s+(\d+)\s+"
        r"(?:pok[eé]mon\s+tcg\s+)?"
        r"booster packs?"
    ),
    (
        r"(\d+)\s+"
        r"(?:pok[eé]mon\s+tcg\s+)?"
        r"booster packs?"
    ),
    r"(\d+)[- ]pack booster",
]


PROMO_PATTERNS = [
    (
        r"includes?\s+(\d+)\s+"
        r"(?:exclusive\s+)?promo cards?"
    ),
    (
        r"contains?\s+(\d+)\s+"
        r"(?:exclusive\s+)?promo cards?"
    ),
    (
        r"(\d+)\s+"
        r"(?:exclusive\s+)?promo cards?"
    ),
]


ACCESSORY_TERMS = {
    "card sleeves": "Card sleeves",
    "deck box": "Deck box",
    "playmat": "Playmat",
    "binder": "Binder",
    "coin": "Collector coin",
    "damage-counter dice": "Damage-counter dice",
    "damage counter dice": "Damage-counter dice",
    "dice": "Dice",
    "condition markers": "Condition markers",
    "dividers": "Card dividers",
    "code card": "Digital code card",
    "energy cards": "Energy cards",
    "collector pin": "Collector pin",
    "oversize card": "Oversize card",
    "oversized card": "Oversize card",
    "sticker": "Stickers",
    "poster": "Poster",
}


SET_MARKERS = [
    "mega evolution",
    "scarlet & violet",
    "scarlet and violet",
    "sword & shield",
    "sword and shield",
    "sun & moon",
    "sun and moon",
]


def extract_product_details(item):
    title = clean_text(
        item.get("title")
    )

    description = clean_text(
        item.get("description")
    )

    searchable_text = (
        f"{title} {description}"
    ).lower()

    pack_count = first_integer_match(
        text=searchable_text,
        patterns=PACK_PATTERNS,
    )

    promo_card_count = first_integer_match(
        text=searchable_text,
        patterns=PROMO_PATTERNS,
    )

    included_accessories = extract_accessories(
        searchable_text
    )

    set_name = extract_set_name(
        title=title,
        description=description,
    )

    fields = {
        "retail_price": item.get(
            "retail_price"
        ),
        "currency": item.get(
            "currency"
        ),
        "release_date": item.get(
            "release_date"
        ),
        "availability": item.get(
            "availability"
        ),
        "sku": item.get("sku"),
        "image_url": item.get(
            "image_url"
        ),
        "pack_count": pack_count,
        "promo_card_count": (
            promo_card_count
        ),
        "set_name": set_name,
    }

    completeness = calculate_completeness(
        fields
    )

    missing_fields = [
        name
        for name, value in fields.items()
        if value in (
            None,
            "",
            [],
            {},
        )
    ]

    summary = build_product_summary(
        item=item,
        pack_count=pack_count,
        promo_card_count=(
            promo_card_count
        ),
        included_accessories=(
            included_accessories
        ),
        set_name=set_name,
    )

    return {
        "pack_count": pack_count,
        "promo_card_count": (
            promo_card_count
        ),
        "included_accessories": (
            included_accessories
        ),
        "set_name": set_name,
        "detail_completeness_score": (
            completeness
        ),
        "detail_completeness_level": (
            completeness_level(
                completeness
            )
        ),
        "missing_detail_fields": (
            missing_fields
        ),
        "product_summary": summary,
    }


def first_integer_match(
    text,
    patterns,
):
    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        try:
            return int(
                match.group(1)
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

    return None


def extract_accessories(text):
    accessories = []

    for term, label in (
        ACCESSORY_TERMS.items()
    ):
        if (
            term in text
            and label not in accessories
        ):
            accessories.append(label)

    return accessories


def extract_set_name(
    title,
    description,
):
    text = (
        f"{title} {description}"
    )

    normalized = text.lower()

    for marker in SET_MARKERS:
        position = normalized.find(
            marker
        )

        if position == -1:
            continue

        candidate = text[
            position:
            position + 100
        ]

        candidate = re.split(
            (
                r"\b(?:elite trainer box|"
                r"booster bundle|"
                r"booster box|"
                r"premium collection|"
                r"special collection|"
                r"collection box|"
                r"booster pack)\b"
            ),
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        candidate = clean_text(
            candidate
        ).strip(
            " :-–—"
        )

        if candidate:
            return candidate

    return None


def calculate_completeness(fields):
    weights = {
        "retail_price": 20,
        "currency": 5,
        "release_date": 15,
        "availability": 15,
        "sku": 15,
        "image_url": 10,
        "pack_count": 8,
        "promo_card_count": 7,
        "set_name": 5,
    }

    score = 0

    for name, weight in (
        weights.items()
    ):
        value = fields.get(name)

        if value not in (
            None,
            "",
            [],
            {},
        ):
            score += weight

    return max(
        0,
        min(score, 100),
    )


def completeness_level(score):
    if score >= 85:
        return "EXCELLENT"

    if score >= 65:
        return "GOOD"

    if score >= 40:
        return "PARTIAL"

    return "LIMITED"


def build_product_summary(
    item,
    pack_count,
    promo_card_count,
    included_accessories,
    set_name,
):
    parts = []

    product_type = item.get(
        "product_type",
        "other",
    )

    parts.append(
        product_type.replace(
            "_",
            " ",
        ).title()
    )

    if set_name:
        parts.append(
            f"Set: {set_name}"
        )

    if pack_count is not None:
        parts.append(
            f"{pack_count} booster pack(s)"
        )

    if promo_card_count is not None:
        parts.append(
            f"{promo_card_count} promo card(s)"
        )

    if included_accessories:
        parts.append(
            "Includes: "
            + ", ".join(
                included_accessories[:5]
            )
        )

    if item.get(
        "pokemon_center_exclusive"
    ):
        parts.append(
            "Pokémon Center exclusive"
        )

    return " | ".join(parts)


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )