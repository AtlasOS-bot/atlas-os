from market.models import MarketResult


class StockXProvider:

    name = "stockx"

    def search(self, item):

        return MarketResult(
            provider="StockX",
            average_price=None,
            lowest_price=None,
            highest_price=None,
            sold_count=None,
            confidence="UNKNOWN",
            notes="StockX integration not connected yet.",
        )