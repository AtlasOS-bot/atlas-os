from scouts.pokemon.release_calendar import (
    build_release_calendar,
)


class PokemonReleaseBrief:

    @staticmethod
    def generate(
        items,
        limit=15,
        today=None,
    ):
        calendar = build_release_calendar(
            items=items,
            today=today,
        )

        selected = calendar[:limit]

        dated_count = len([
            entry
            for entry in calendar
            if entry.get(
                "release_date"
            )
        ])

        lines = [
            "=" * 56,
            "ATLAS POKÉMON RELEASE CALENDAR",
            "=" * 56,
            (
                f"Products analyzed: "
                f"{len(calendar)}"
            ),
            (
                f"Products with dates: "
                f"{dated_count}"
            ),
            (
                f"Top calendar entries shown: "
                f"{len(selected)}"
            ),
            "",
        ]

        if not selected:
            lines.append(
                "No Pokémon release entries found."
            )

            return "\n".join(lines)

        for position, entry in enumerate(
            selected,
            start=1,
        ):
            release_date = (
                entry.get("release_date")
                or "Unknown"
            )

            days = entry.get(
                "days_until_release"
            )

            if days is None:
                timing = "Timing unknown"

            elif days == 0:
                timing = "Today"

            elif days > 0:
                timing = (
                    f"In {days} day(s)"
                )

            else:
                timing = (
                    f"{abs(days)} day(s) ago"
                )

            lines.extend([
                (
                    f"#{position} — "
                    f"{entry['action_window']}"
                ),
                entry["title"],
                (
                    f"Release date: "
                    f"{release_date}"
                ),
                f"Timing: {timing}",
                (
                    f"Urgency: "
                    f"{entry['urgency_score']}/100"
                ),
                (
                    f"Product type: "
                    f"{entry['product_type']}"
                ),
                (
                    f"Recommended action: "
                    f"{entry['recommended_action']}"
                ),
                (
                    f"Reason: "
                    f"{entry['reason']}"
                ),
                "",
            ])

        return "\n".join(lines)