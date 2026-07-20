"""
Text normalization and deterministic deduplication for collector
opportunities. Deliberately self-contained (no dependency on any
scouts.* brand module) so this foundation stays reusable across every
ecosystem Atlas tracks, not just Pokémon.
"""


def normalize_text(value):
    if not value:
        return ""

    characters = []

    for character in str(value).strip().lower():
        if character.isalnum():
            characters.append(character)
        else:
            characters.append(" ")

    return " ".join(
        "".join(characters).split()
    )


def normalize_date(value):
    if not value:
        return ""

    # Keep only the date portion if a full timestamp was supplied,
    # so "2026-08-01" and "2026-08-01T00:00:00Z" dedup identically.
    text = str(value).strip()

    return normalize_text(text[:10])


def compute_dedup_key(
    brand=None,
    franchise=None,
    product_name=None,
    collaboration_partner=None,
    release_date=None,
    retailer=None,
):
    """
    Deterministic key from normalized brand + franchise + product
    name + collaboration partner + release date + retailer. Two
    reports of the same real-world product/drop from different
    sources normalize to the same key, regardless of casing,
    punctuation, or minor wording differences in the source text.
    """
    parts = [
        normalize_text(brand),
        normalize_text(franchise),
        normalize_text(product_name),
        normalize_text(collaboration_partner),
        normalize_date(release_date),
        normalize_text(retailer),
    ]

    return "|".join(parts)
