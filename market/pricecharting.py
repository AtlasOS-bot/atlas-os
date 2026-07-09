from market.models import MarketResult


class PriceChartingProvider:

    name = "pricecharting"

    def search(self, item):

        return MarketResult(
            provider="PriceCharting",
            average_price=None,
            lowest_price=None,
            highest_price=None,
            sold_count=None,
            confidence="UNKNOWN",
            notes="PriceCharting integration not connected yet.",
        )