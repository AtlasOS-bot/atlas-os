from signals.base import AtlasSignal


class OfficialSourceSignal(AtlasSignal):
    name = "official_source"
    weight = 12

    def detect(self, item):
        return bool(item.get("url"))

    def explain(self, item):
        return "Official source URL is available."