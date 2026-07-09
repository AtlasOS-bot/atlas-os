from signals.base import AtlasSignal


class ShockDropSignal(AtlasSignal):
    name = "shock_drop"
    weight = 14

    def detect(self, item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        return "shock drop" in text

    def explain(self, item):
        return "Shock drop language detected. Atlas treats this as a high-urgency signal."