import re


ONE_PIECE_CODE_PATTERNS = [
    r"\bOP[- ]?\d{1,2}\b",
    r"\bEB[- ]?\d{1,2}\b",
    r"\bST[- ]?\d{1,2}\b",
    r"\bPRB[- ]?\d{1,2}\b",
    r"\bDP[- ]?\d{1,2}\b",
    r"\bTS[- ]?\d{1,2}\b",
    r"\bDF[- ]?\d{1,2}\b",
    r"\bP[- ]?\d{1,3}\b",
]


def parse_one_piece_item(
    title,
    url,
    description="",
    **extra_fields,
):
    cleaned_title = clean_text(
        title
    )

    cleaned_description = clean_text(
        description
    )

    searchable_text = (
        f"{cleaned_title} "
        f"{cleaned_description}"
    )

    product_codes = (
        extract_product_codes(
            searchable_text
        )
    )

    item = {
        "brand": (
            "One Piece Card Game"
        ),
        "title": cleaned_title,
        "description": (
            cleaned_description
        ),
        "url": url,
        "category": "one_piece",
        "source": "one_piece",
        "tcg_name": "one_piece",
        "product_codes": (
            product_codes
        ),
        "set_codes": (
            product_codes
        ),
        "primary_set_code": (
            product_codes[0]
            if product_codes
            else None
        ),
    }

    for key, value in (
        extra_fields.items()
    ):
        if value not in (
            None,
            "",
            [],
            {},
        ):
            item[key] = value

    return item


def extract_product_codes(text):
    codes = []

    for pattern in (
        ONE_PIECE_CODE_PATTERNS
    ):
        matches = re.findall(
            pattern,
            text or "",
            flags=re.IGNORECASE,
        )

        for match in matches:
            normalized = (
                normalize_product_code(
                    match
                )
            )

            if normalized not in codes:
                codes.append(
                    normalized
                )

    return codes


def normalize_product_code(value):
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

    compact_match = re.fullmatch(
        (
            r"(OP|EB|ST|PRB|DP|"
            r"TS|DF|P)(\d+)"
        ),
        normalized,
    )

    if compact_match:
        prefix = compact_match.group(1)
        number = compact_match.group(2)

        normalized = (
            f"{prefix}-{number}"
        )

    return normalized


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )