import re

from scouts.tcg.profiles import (
    get_tcg_profile,
    normalize_tcg_name,
)


GENERIC_SET_CODE_PATTERNS = {
    "one_piece": [
        r"\bOP[- ]?\d{1,2}\b",
        r"\bEB[- ]?\d{1,2}\b",
        r"\bST[- ]?\d{1,2}\b",
        r"\bPRB[- ]?\d{1,2}\b",
        r"\bDP[- ]?\d{1,2}\b",
        r"\bTS[- ]?\d{1,2}\b",
        r"\bDF[- ]?\d{1,2}\b",
        r"\bP[- ]?\d{1,3}\b",
    ],
    "lorcana": [
        r"\bD23\b",
        r"\bDisney100\b",
        r"\bDisney 100\b",
    ],
}


def classify_tcg_product(
    item,
    tcg_name,
):
    normalized_tcg = normalize_tcg_name(
        tcg_name
    )

    profile = get_tcg_profile(
        normalized_tcg
    )

    title = clean_text(
        item.get("title")
    )

    description = clean_text(
        item.get("description")
    )

    searchable_text = (
        f"{title} {description}"
    ).lower()

    product_type = "other"

    matched_product_terms = []

    for candidate_type, terms in profile[
        "product_rules"
    ]:
        matches = [
            term
            for term in terms
            if term in searchable_text
        ]

        if not matches:
            continue

        product_type = candidate_type
        matched_product_terms = matches
        break

    set_codes = extract_set_codes(
        text=(
            f"{title} {description}"
        ),
        tcg_name=normalized_tcg,
    )

    is_sealed = (
        product_type
        in profile["sealed_types"]
    )

    limited_release = contains_any(
        searchable_text,
        [
            "limited",
            "exclusive",
            "special edition",
            "anniversary",
            "while supplies last",
            "event exclusive",
            "tournament exclusive",
            "premium bandai",
        ],
    )

    promo_included = contains_any(
        searchable_text,
        [
            "promo card",
            "promotion card",
            "promotional card",
            "exclusive card",
            "winner card",
        ],
    )

    collector_variant = contains_any(
        searchable_text,
        [
            "enchanted",
            "serialized",
            "manga rare",
            "alternate art",
            "alt art",
            "parallel",
            "special card",
            "secret rare",
            "foil",
        ],
    )

    return {
        "tcg_name": normalized_tcg,
        "brand": profile["brand"],
        "product_type": product_type,
        "matched_product_terms": (
            matched_product_terms
        ),
        "set_codes": set_codes,
        "primary_set_code": (
            set_codes[0]
            if set_codes
            else None
        ),
        "sealed_product": is_sealed,
        "limited_release": limited_release,
        "promo_included": promo_included,
        "collector_variant": (
            collector_variant
        ),
    }


def extract_set_codes(
    text,
    tcg_name,
):
    normalized_tcg = normalize_tcg_name(
        tcg_name
    )

    patterns = (
        GENERIC_SET_CODE_PATTERNS.get(
            normalized_tcg,
            [],
        )
    )

    codes = []

    for pattern in patterns:
        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:
            normalized = normalize_set_code(
                match
            )

            if normalized not in codes:
                codes.append(normalized)

    return codes


def normalize_set_code(value):
    normalized = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "-")
    )

    normalized = re.sub(
        r"-+",
        "-",
        normalized,
    )

    if re.fullmatch(
        r"(OP|EB|ST|PRB|DP|TS|DF|P)\d+",
        normalized,
    ):
        prefix = re.match(
            r"[A-Z]+",
            normalized,
        ).group()

        number = re.search(
            r"\d+",
            normalized,
        ).group()

        normalized = (
            f"{prefix}-{number}"
        )

    return normalized


def contains_any(
    text,
    terms,
):
    return any(
        term in text
        for term in terms
    )


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )