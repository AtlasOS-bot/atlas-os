from reasoning.engine import reason


class AtlasBrain:

    @staticmethod
    def analyze(item, category="general"):
        return reason(
            item=item,
            category=category,
        )