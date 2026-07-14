class TcgMoneyBrief:

    @staticmethod
    def generate(
        board,
        limit=15,
    ):
        top_items = (
            board.get(
                "top_overall",
                [],
            )[:limit]
        )

        lines = [
            "=" * 64,
            "ATLAS CROSS-TCG MONEY BOARD",
            "=" * 64,
            (
                f"Products ranked: "
                f"{board.get('count', 0)}"
            ),
            (
                f"Critical: "
                f"{board.get('critical_count', 0)}"
            ),
            (
                f"High: "
                f"{board.get('high_count', 0)}"
            ),
            (
                f"Medium: "
                f"{board.get('medium_count', 0)}"
            ),
            (
                f"Watch: "
                f"{board.get('watch_count', 0)}"
            ),
            "",
        ]

        if not top_items:
            lines.append(
                "No ranked TCG products yet."
            )

            return "\n".join(
                lines
            )

        for position, item in enumerate(
            top_items,
            start=1,
        ):
            strategy = (
                item.get(
                    "best_strategy"
                )
                or {}
            )

            if isinstance(
                strategy,
                dict,
            ):
                strategy_name = (
                    strategy.get(
                        "strategy",
                        "UNKNOWN",
                    )
                )

            else:
                strategy_name = str(
                    strategy
                )

            lines.extend([
                (
                    f"#{position} — "
                    f"{item.get('opportunity_tier', 'WATCH')}"
                ),
                (
                    item.get(
                        "title",
                        "Unknown product",
                    )
                ),
                (
                    f"Game: "
                    f"{item.get('game_name', 'Unknown')}"
                ),
                (
                    f"Opportunity: "
                    f"{item.get('opportunity_score', 0)}/100"
                ),
                (
                    f"Strategy: "
                    f"{strategy_name}"
                ),
                (
                    f"Collector: "
                    f"{item.get('collector_score', 0)}/100"
                ),
                (
                    f"Flip: "
                    f"{item.get('flip_score', 0)}/100"
                ),
                (
                    f"Hold: "
                    f"{item.get('hold_score', 0)}/100"
                ),
                (
                    f"Sleeper: "
                    f"{item.get('sleeper_score', 0)}/100"
                ),
                (
                    f"Action: "
                    f"{item.get('recommended_action', 'MONITOR')}"
                ),
                (
                    f"URL: "
                    f"{item.get('url', 'Unknown')}"
                ),
                "",
            ])

        return "\n".join(
            lines
        )