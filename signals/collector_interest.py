from signals.base import AtlasSignal


class CollectorInterestSignal(AtlasSignal):
    name = "collector_interest"
    weight = 10

    def detect(self, item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        return any(term in text for term in ["promo", "collector", "anniversary", "exclusive", "limited"])

    def explain(self, item):
        return "Collector-interest language detected."