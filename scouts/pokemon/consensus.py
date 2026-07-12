from scouts.pokemon.identity import (
    same_product,
)


TRUSTED_SOURCE_WEIGHTS = {
    "pokemon_center_new_releases": 25,
    "pokemon_center_tcg": 25,
    "pokemon_news": 20,
    "pokemon_tcg_gallery": 20,
}


def build_consensus(items):
    groups = []

    for item in items:
        matching_group = None

        for group in groups:
            if same_product(
                item,
                group[0],
            ):
                matching_group = group
                break

        if matching_group is None:
            groups.append([item])
        else:
            matching_group.append(item)

    return [
        consensus_item(group)
        for group in groups
    ]


def consensus_item(group):
    primary = choose_primary_item(
        group
    )

    merged = dict(primary)

    sources = []
    source_urls = []
    discovery_methods = []

    for item in group:
        append_unique(
            sources,
            item.get("source"),
        )

        for source in (
            item.get("sources")
            or []
        ):
            append_unique(
                sources,
                source,
            )

        append_unique(
            source_urls,
            item.get("source_url"),
        )

        append_unique(
            discovery_methods,
            item.get("discovery_method"),
        )

        merged = merge_missing_fields(
            merged,
            item,
        )

    consensus = calculate_consensus_score(
        sources=sources,
        confirmation_count=len(group),
    )

    merged["sources"] = sources
    merged["source_urls"] = source_urls
    merged["discovery_methods"] = (
        discovery_methods
    )

    merged["confirmation_count"] = (
        len(group)
    )

    merged["source_consensus"] = (
        consensus
    )

    merged["consensus_score"] = (
        consensus["score"]
    )

    merged["consensus_level"] = (
        consensus["level"]
    )

    return merged


def choose_primary_item(group):
    return max(
        group,
        key=item_quality_score,
    )


def item_quality_score(item):
    score = 0

    if item.get("sku"):
        score += 25

    if item.get("retail_price") is not None:
        score += 20

    if item.get("release_date"):
        score += 15

    if item.get("availability"):
        score += 10

    if item.get("image_url"):
        score += 8

    if item.get("description"):
        score += min(
            len(item["description"])
            // 50,
            10,
        )

    if (
        item.get("discovery_method")
        == "structured_json"
    ):
        score += 12

    return score


def merge_missing_fields(
    existing,
    incoming,
):
    merged = dict(existing)

    for key, value in incoming.items():
        if value in (
            None,
            "",
            [],
            {},
        ):
            continue

        current = merged.get(key)

        if current in (
            None,
            "",
            [],
            {},
        ):
            merged[key] = value

        elif (
            key == "description"
            and len(str(value))
            > len(str(current))
        ):
            merged[key] = value

    return merged


def calculate_consensus_score(
    sources,
    confirmation_count,
):
    score = 10
    reasons = []

    for source in sources:
        weight = TRUSTED_SOURCE_WEIGHTS.get(
            source,
            5,
        )

        score += weight

        reasons.append(
            f"{source} added {weight} "
            "source-trust point(s)."
        )

    if confirmation_count >= 4:
        score += 20
        reasons.append(
            "Four or more confirmations "
            "strongly support the product identity."
        )

    elif confirmation_count == 3:
        score += 15
        reasons.append(
            "Three confirmations support "
            "the product identity."
        )

    elif confirmation_count == 2:
        score += 8
        reasons.append(
            "Two confirmations support "
            "the product identity."
        )

    score = max(
        0,
        min(round(score), 100),
    )

    return {
        "score": score,
        "level": consensus_level(score),
        "confidence": consensus_confidence(
            source_count=len(sources),
            confirmation_count=confirmation_count,
        ),
        "source_count": len(sources),
        "confirmation_count": (
            confirmation_count
        ),
        "reasons": reasons,
    }


def consensus_level(score):
    if score >= 85:
        return "VERY HIGH"

    if score >= 70:
        return "HIGH"

    if score >= 50:
        return "MEDIUM"

    return "LOW"


def consensus_confidence(
    source_count,
    confirmation_count,
):
    if (
        source_count >= 3
        and confirmation_count >= 3
    ):
        return "VERY HIGH"

    if (
        source_count >= 2
        and confirmation_count >= 2
    ):
        return "HIGH"

    if source_count >= 1:
        return "MEDIUM"

    return "LOW"


def append_unique(
    values,
    candidate,
):
    if (
        candidate
        and candidate not in values
    ):
        values.append(candidate)