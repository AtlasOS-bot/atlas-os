from signals.base import AtlasSignal


class RestockSignal(AtlasSignal):
    name = "restock"
    weight = -8

    def detect(self, item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        return "restock" in text or "available again" in text

    def explain(self, item):
        return "Restock language detected. Atlas treats this as a watch signal, not an automatic buy."