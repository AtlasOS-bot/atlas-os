from popularity.engine import PopularityEngine
from scouts.pokemon.classifier import (
    calculate_release_urgency,
    classify_pokemon_product,
)
from scouts.pokemon.collector_intelligence import (
    calculate_collector_intelligence,
)
from scouts.pokemon.investment_intelligence import (
    calculate_investment_intelligence,
)


def enrich_pokemon_item(item):
    enriched = dict(item)

    classification = classify_pokemon_product(
        enriched
    )

    enriched.update(
        classification
    )

    release_urgency = calculate_release_urgency(
        enriched
    )

    enriched["release_urgency"] = (
        release_urgency
    )

    popularity = PopularityEngine.analyze(
        item=enriched,
        category="pokemon",
    )

    enriched["popularity"] = popularity
    enriched["popularity_score"] = (
        popularity["score"]
    )
    enriched["popularity_level"] = (
        popularity["level"]
    )

    collector_intelligence = (
        calculate_collector_intelligence(
            enriched
        )
    )

    enriched["collector_intelligence"] = (
        collector_intelligence
    )

    enriched["collector_score"] = (
        collector_intelligence["score"]
    )

    enriched["collector_level"] = (
        collector_intelligence["level"]
    )

    enriched["hold_profile"] = (
        collector_intelligence[
            "hold_profile"
        ]
    )

    investment_intelligence = (
        calculate_investment_intelligence(
            enriched
        )
    )

    enriched["investment_intelligence"] = (
        investment_intelligence
    )

    enriched["flip_score"] = (
        investment_intelligence[
            "flip"
        ]["score"]
    )

    enriched["hold_score"] = (
        investment_intelligence[
            "hold"
        ]["score"]
    )

    enriched["sleeper_score"] = (
        investment_intelligence[
            "sleeper"
        ]["score"]
    )

    enriched["best_strategy"] = (
        investment_intelligence[
            "best_strategy"
        ]
    )

    return enriched