from dataclasses import dataclass


@dataclass
class SignalResult:
    detected: bool
    weight: int
    reason: str
    signal: str


class AtlasSignal:

    name = "signal"
    weight = 0

    def detect(self, item):
        return False

    def explain(self, item):
        return f"{self.name} detected."

    def evaluate(self, item):
        detected = self.detect(item)

        return SignalResult(
            detected=detected,
            weight=self.weight if detected else 0,
            reason=self.explain(item),
            signal=self.name,
        )