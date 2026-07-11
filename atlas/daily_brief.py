from atlas.mission import MissionBrief
from atlas.ranking import OpportunityRanker


class DailyBrief:

    @staticmethod
    def generate(opportunities, limit=10):
        ranked = OpportunityRanker.rank(opportunities)
        selected = ranked[:limit]

        lines = [
            "=" * 50,
            "ATLAS DAILY OPPORTUNITY BRIEF",
            "=" * 50,
            f"Opportunities analyzed: {len(opportunities)}",
            f"Top opportunities shown: {len(selected)}",
            "",
        ]

        for position, opportunity in enumerate(selected, start=1):
            item = opportunity.get("item", {})
            analysis = opportunity.get("analysis", {})

            lines.append(f"#{position}")
            lines.append(
                MissionBrief.generate(
                    item=item,
                    analysis=analysis,
                )
            )
            lines.append("")

        return "\n".join(lines)