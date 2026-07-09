class MarketProvider:
    name = "provider"

    def search(self, item):
        raise NotImplementedError("Market providers must implement search().")