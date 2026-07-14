PRIORITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "IGNORE": 0,
}


GAME_NAMES = {
    "pokemon": "Pokémon",
    "lorcana": "Disney Lorcana",
    "one_piece": "One Piece",
}


class TcgAlertBrief:

    @staticmethod
    def generate(
        alerts,
        limit=20,
    ):
        ranked = sorted(
            alerts,
            key=ranking_key,
            reverse=True,
        )[:limit]

        lines = [
            "=" * 66,
            "ATLAS CROSS-TCG ALERT CENTER",
            "=" * 66,
            (
                f"Active alerts: "
                f"{len(alerts)}"
            ),
            (
                f"Top alerts shown: "
                f"{len(ranked)}"
            ),
            "",
        ]

        if not ranked:
            lines.append(
                "No active cross-TCG alerts."
            )

            return "\n".join(
                lines
            )

        for position, alert in enumerate(
            ranked,
            start=1,
        ):
            category = (
                str(
                    alert.get(
                        "category",
                        "unknown",
                    )
                )
                .strip()
                .lower()
            )

            game_name = (
                alert.get(
                    "game_name"
                )
                or GAME_NAMES.get(
                    category,
                    category.replace(
                        "_",
                        " ",
                    ).title(),
                )
            )

            lines.extend([
                (
                    f"#{position} — "
                    f"{alert.get('priority', 'LOW')}"
                ),
                (
                    alert.get(
                        "title",
                        "Unknown product",
                    )
                ),
                (
                    f"Game: "
                    f"{game_name}"
                ),
                (
                    f"Event: "
                    f"{alert.get('event', 'UNKNOWN')}"
                ),
                (
                    f"Alert score: "
                    f"{alert.get('score', 0)}/100"
                ),
                (
                    f"Opportunity: "
                    f"{alert.get('opportunity_score', 0)}/100 "
                    f"({alert.get('opportunity_tier', 'WATCH')})"
                ),
                (
                    f"Strategy: "
                    f"{alert.get('strategy', 'UNKNOWN')}"
                ),
                (
                    f"Flip: "
                    f"{alert.get('flip_score', 0)}/100"
                ),
                (
                    f"Hold: "
                    f"{alert.get('hold_score', 0)}/100"
                ),
                (
                    f"Action: "
                    f"{alert.get('action', 'MONITOR')}"
                ),
                (
                    f"Reason: "
                    f"{alert.get('reason', 'No reason recorded.')}"
                ),
                (
                    f"URL: "
                    f"{alert.get('url', 'Unknown')}"
                ),
                "",
            ])

        return "\n".join(
            lines
        )


def ranking_key(alert):
    return (
        PRIORITY_ORDER.get(
            alert.get(
                "priority",
                "IGNORE",
            ),
            0,
        ),
        number_value(
            alert.get(
                "score"
            )
        ),
        number_value(
            alert.get(
                "opportunity_score"
            )
        ),
        number_value(
            alert.get(
                "flip_score"
            )
        ),
        number_value(
            alert.get(
                "hold_score"
            )
        ),
    )


def number_value(value):
    try:
        return float(
            value or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0.0