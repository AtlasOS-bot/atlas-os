from signals.base import AtlasSignal


class HistoricalPatternSignal(AtlasSignal):
    name = "historical_pattern"
    weight = 8

    def detect(self, item):
        return bool(item.get("patterns"))

    def explain(self, item):
        return "Historical pattern signal detected."