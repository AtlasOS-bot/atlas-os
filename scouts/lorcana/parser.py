import re


PRODUCT_CODE_PATTERNS = [
    r"\bD23\b",
    r"\bDisney\s*100\b",
]


def parse_lorcana_item(
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

    item = {
        "brand": "Disney Lorcana",
        "title": cleaned_title,
        "description": (
            cleaned_description
        ),
        "url": url,
        "category": "lorcana",
        "source": "lorcana",
        "tcg_name": "lorcana",
        "product_codes": (
            extract_product_codes(
                f"{cleaned_title} "
                f"{cleaned_description}"
            )
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

    for pattern in PRODUCT_CODE_PATTERNS:
        matches = re.findall(
            pattern,
            text or "",
            flags=re.IGNORECASE,
        )

        for match in matches:
            normalized = (
                str(match)
                .strip()
                .upper()
                .replace(" ", "")
            )

            if normalized not in codes:
                codes.append(normalized)

    return codes


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )