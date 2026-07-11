from scouts.pokemon.classifier import (
    calculate_release_urgency,
    classify_pokemon_product,
)


def enrich_pokemon_item(item):
    enriched = dict(item)

    classification = (
        classify_pokemon_product(
            enriched
        )
    )

    release_urgency = (
        calculate_release_urgency(
            enriched
        )
    )

    enriched.update(
        classification
    )

    enriched["release_urgency"] = (
        release_urgency
    )

    return enriched