from popularity.models import PopularityResult
from popularity.pokemon import (
    analyze_pokemon_popularity,
)


class PopularityEngine:

    @staticmethod
    def analyze(
        item,
        category="general",
    ):
        normalized_category = (
            category
            or item.get("category")
            or "general"
        ).lower()

        if normalized_category == "pokemon":
            result = analyze_pokemon_popularity(
                item
            )

        else:
            result = {
                "score": 10,
                "level": "LOW",
                "confidence": "LOW",
                "source_count": 0,
                "signals": [],
                "reasons": [
                    (
                        "No category-specific popularity model "
                        "is available yet."
                    )
                ],
            }

        return PopularityResult(
            score=result["score"],
            level=result["level"],
            confidence=result["confidence"],
            source_count=result["source_count"],
            signals=result["signals"],
            reasons=result["reasons"],
        ).to_dict()