from signals.base import AtlasSignal


class ReprintSignal(AtlasSignal):
    name = "reprint"
    weight = -12

    def detect(self, item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        return "reprint" in text

    def explain(self, item):
        return "Reprint risk detected. Prices may soften if supply returns."