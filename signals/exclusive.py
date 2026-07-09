from signals.base import AtlasSignal


class ExclusiveSignal(AtlasSignal):
    name = "exclusive"
    weight = 10

    def detect(self, item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        return "exclusive" in text or "exclusive access" in text

    def explain(self, item):
        return "Exclusive product language detected."