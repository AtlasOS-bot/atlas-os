from signals.base import (
    AtlasSignal,
    SignalResult,
)


class InvestmentStrategySignal(
    AtlasSignal
):
    name = "investment_strategy"

    def detect(self, item):
        strategy = (
            item.get("best_strategy")
            or {}
        )

        return strategy.get(
            "score",
            0,
        ) >= 55

    def evaluate(self, item):
        strategy = (
            item.get("best_strategy")
            or {}
        )

        score = strategy.get(
            "score",
            0,
        )

        detected = self.detect(item)

        if score >= 85:
            weight = 14

        elif score >= 70:
            weight = 10

        elif score >= 55:
            weight = 7

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
                f"Best investment strategy: "
                f"{strategy.get('strategy', 'UNKNOWN')} "
                f"with a score of {score}/100."
            ),
            signal=self.name,
        )