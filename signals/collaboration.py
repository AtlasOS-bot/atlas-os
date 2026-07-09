from signals.base import AtlasSignal


class CollaborationSignal(AtlasSignal):
    name = "collaboration"
    weight = 10

    def detect(self, item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        return any(term in text for term in ["collab", "collaboration", "travis scott", "off-white", "kobe"])

    def explain(self, item):
        return "Collaboration or high-demand partner signal detected."