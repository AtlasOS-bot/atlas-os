import time


class MarketCache:

    def __init__(self, ttl=900):
        self.ttl = ttl
        self.cache = {}

    def get(self, key):

        if key not in self.cache:
            return None

        entry = self.cache[key]

        if time.time() - entry["time"] > self.ttl:
            del self.cache[key]
            return None

        return entry["value"]

    def set(self, key, value):

        self.cache[key] = {
            "time": time.time(),
            "value": value,
        }


market_cache = MarketCache()