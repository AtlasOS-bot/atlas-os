from market.models import MarketResult


class EbayProvider:

    name = "ebay"

    def search(self, item):

        return MarketResult(
            provider="eBay",
            average_price=None,
            lowest_price=None,
            highest_price=None,
            sold_count=None,
            confidence="UNKNOWN",
            notes="eBay integration not connected yet.",
        )