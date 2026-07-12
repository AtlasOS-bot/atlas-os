from scouts.pokemon.alert_queue import (
    PokemonAlertQueue,
)


class PokemonAlertBrief:

    @staticmethod
    def generate(
        alerts,
        limit=10,
    ):
        ranked = PokemonAlertQueue.top(
            alerts=alerts,
            limit=limit,
        )

        lines = [
            "=" * 52,
            "ATLAS POKÉMON ALERT BRIEF",
            "=" * 52,
            f"Active alerts: {len(alerts)}",
            f"Top alerts shown: {len(ranked)}",
            "",
        ]

        if not ranked:
            lines.append(
                "No active Pokémon alerts."
            )

            return "\n".join(lines)

        for position, alert in enumerate(
            ranked,
            start=1,
        ):
            lines.extend([
                f"#{position} — "
                f"{alert.get('priority', 'UNKNOWN')}",
                (
                    alert.get("title")
                    or "Unknown product"
                ),
                (
                    f"Event: "
                    f"{alert.get('event', 'UNKNOWN')}"
                ),
                (
                    f"Alert Score: "
                    f"{alert.get('score', 0)}/100"
                ),
                (
                    f"Action: "
                    f"{alert.get('action', 'NO ACTION')}"
                ),
                (
                    f"Strategy: "
                    f"{alert.get('best_strategy', 'UNKNOWN')}"
                ),
                (
                    f"Flip: "
                    f"{alert.get('flip_score', 0) or 0}/100"
                ),
                (
                    f"Hold: "
                    f"{alert.get('hold_score', 0) or 0}/100"
                ),
                (
                    f"Collector: "
                    f"{alert.get('collector_score', 0) or 0}/100"
                ),
                (
                    f"Reason: "
                    f"{alert.get('reason', 'No reason recorded.')}"
                ),
                "",
            ])

        return "\n".join(lines)