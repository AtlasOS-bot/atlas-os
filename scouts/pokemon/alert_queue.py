PRIORITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "IGNORE": 0,
}


class PokemonAlertQueue:

    @staticmethod
    def rank(alerts):
        return sorted(
            alerts,
            key=PokemonAlertQueue._ranking_key,
            reverse=True,
        )

    @staticmethod
    def _ranking_key(alert):
        return (
            PRIORITY_ORDER.get(
                alert.get(
                    "priority",
                    "IGNORE",
                ),
                0,
            ),
            alert.get(
                "score",
                0,
            ),
            alert.get(
                "flip_score",
                0,
            )
            or 0,
            alert.get(
                "hold_score",
                0,
            )
            or 0,
            alert.get(
                "collector_score",
                0,
            )
            or 0,
        )

    @staticmethod
    def top(
        alerts,
        limit=10,
    ):
        return PokemonAlertQueue.rank(
            alerts
        )[:limit]