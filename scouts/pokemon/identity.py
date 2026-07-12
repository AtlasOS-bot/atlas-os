import re
import unicodedata


NOISE_WORDS = {
    "pokemon",
    "pokémon",
    "the",
    "a",
    "an",
    "new",
    "official",
    "trading",
    "card",
    "game",
    "tcg",
    "product",
    "with",
    "and",
    "edition",
}


PRODUCT_TYPE_TERMS = {
    "elite trainer box": "etb",
    "booster bundle": "booster_bundle",
    "booster box": "booster_box",
    "premium collection": "premium_collection",
    "special collection": "special_collection",
    "collection box": "collection_box",
    "mini tin": "mini_tin",
    "tin": "tin",
    "plush": "plush",
    "figure": "figure",
    "pin": "pin",
}


def normalize_identity_text(value):
    text = unicodedata.normalize(
        "NFKD",
        value or "",
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    text = text.lower()

    text = text.replace(
        "pokémon",
        "pokemon",
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    words = [
        word
        for word in text.split()
        if word not in NOISE_WORDS
    ]

    return " ".join(words)


def normalize_sku(value):
    normalized = (
        str(value)
        .strip()
        .lower()
    )

    normalized = re.sub(
        r"[\s_]+",
        "-",
        normalized,
    )

    normalized = re.sub(
        r"[^a-z0-9-]+",
        "",
        normalized,
    )

    normalized = re.sub(
        r"-+",
        "-",
        normalized,
    )

    return normalized.strip("-")


def detect_identity_product_type(item):
    text = normalize_identity_text(
        f"{item.get('title', '')} "
        f"{item.get('description', '')}"
    )

    for term, product_type in PRODUCT_TYPE_TERMS.items():
        normalized_term = normalize_identity_text(
            term
        )

        if normalized_term in text:
            return product_type

    return (
        item.get("product_type")
        or "unknown"
    )


def extract_identity_tokens(item):
    normalized_title = normalize_identity_text(
        item.get("title", "")
    )

    return {
        token
        for token in normalized_title.split()
        if len(token) >= 3
    }


def canonical_product_key(item):
    sku = item.get("sku")

    if sku:
        normalized_sku = normalize_sku(
            sku
        )

        if normalized_sku:
            return f"sku:{normalized_sku}"

    product_type = detect_identity_product_type(
        item
    )

    tokens = sorted(
        extract_identity_tokens(item)
    )

    if not tokens:
        return None

    return (
        f"{product_type}:"
        + "-".join(tokens)
    )


def identity_similarity(
    first,
    second,
):
    first_tokens = extract_identity_tokens(
        first
    )

    second_tokens = extract_identity_tokens(
        second
    )

    if not first_tokens or not second_tokens:
        return 0.0

    intersection = (
        first_tokens
        & second_tokens
    )

    union = (
        first_tokens
        | second_tokens
    )

    token_similarity = (
        len(intersection)
        / len(union)
    )

    first_type = detect_identity_product_type(
        first
    )

    second_type = detect_identity_product_type(
        second
    )

    type_bonus = (
        0.15
        if (
            first_type == second_type
            and first_type != "unknown"
        )
        else 0
    )

    return min(
        round(
            token_similarity + type_bonus,
            3,
        ),
        1.0,
    )


def same_product(
    first,
    second,
    threshold=0.72,
):
    first_sku = first.get("sku")
    second_sku = second.get("sku")

    if first_sku and second_sku:
        if (
            normalize_sku(first_sku)
            == normalize_sku(second_sku)
        ):
            return True

    return (
        identity_similarity(
            first,
            second,
        )
        >= threshold
    )