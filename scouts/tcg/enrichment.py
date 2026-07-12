from scouts.tcg.classifier import (
    classify_tcg_product,
)
from scouts.tcg.intelligence import (
    calculate_tcg_intelligence,
)


def enrich_tcg_item(
    item,
    tcg_name,
):
    enriched = dict(item)

    classification = (
        classify_tcg_product(
            item=enriched,
            tcg_name=tcg_name,
        )
    )

    enriched.update(
        classification
    )

    intelligence = (
        calculate_tcg_intelligence(
            item=enriched,
            tcg_name=tcg_name,
        )
    )

    enriched[
        "tcg_intelligence"
    ] = intelligence

    enriched[
        "collector_score"
    ] = intelligence[
        "collector_score"
    ]

    enriched[
        "collector_level"
    ] = intelligence[
        "collector_level"
    ]

    enriched[
        "popularity_score"
    ] = intelligence[
        "popularity_score"
    ]

    enriched[
        "popularity_level"
    ] = intelligence[
        "popularity_level"
    ]

    enriched[
        "flip_score"
    ] = intelligence[
        "flip_score"
    ]

    enriched[
        "hold_score"
    ] = intelligence[
        "hold_score"
    ]

    enriched[
        "sleeper_score"
    ] = intelligence[
        "sleeper_score"
    ]

    enriched[
        "best_strategy"
    ] = intelligence[
        "best_strategy"
    ]

    return enriched