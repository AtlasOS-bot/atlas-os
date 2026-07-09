from signals.base import AtlasSignal


class LimitedReleaseSignal(AtlasSignal):
    name = "limited_release"
    weight = 12

    def detect(self, item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        return "limited" in text

    def explain(self, item):
        return "Limited release language detected."