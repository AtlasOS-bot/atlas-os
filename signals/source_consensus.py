from signals.base import (
    AtlasSignal,
    SignalResult,
)


class SourceConsensusSignal(
    AtlasSignal
):
    name = "source_consensus"

    def detect(self, item):
        return (
            item.get(
                "consensus_score",
                0,
            )
            >= 50
        )

    def evaluate(self, item):
        score = item.get(
            "consensus_score",
            0,
        )

        detected = self.detect(item)

        if score >= 85:
            weight = 14

        elif score >= 70:
            weight = 10

        elif score >= 50:
            weight = 6

        else:
            weight = 0

        return SignalResult(
            detected=detected,
            weight=(
                weight
                if detected
                else 0
            ),
            reason=(
                f"Official source consensus score "
                f"is {score}/100 across "
                f"{item.get('confirmation_count', 1)} "
                "confirmation(s)."
            ),
            signal=self.name,
        )