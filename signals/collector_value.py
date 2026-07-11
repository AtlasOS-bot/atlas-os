from signals.base import (
    AtlasSignal,
    SignalResult,
)


class CollectorValueSignal(AtlasSignal):
    name = "collector_value"

    def detect(self, item):
        return (
            item.get(
                "collector_score",
                0,
            )
            >= 35
        )

    def evaluate(self, item):
        score = item.get(
            "collector_score",
            0,
        )

        detected = self.detect(item)

        if score >= 85:
            weight = 16

        elif score >= 70:
            weight = 12

        elif score >= 55:
            weight = 8

        elif score >= 35:
            weight = 4

        else:
            weight = 0

        return SignalResult(
            detected=detected,
            weight=weight if detected else 0,
            reason=(
                f"Pokémon collector score is "
                f"{score}/100 "
                f"({item.get('collector_level', 'UNKNOWN')})."
            ),
            signal=self.name,
        )