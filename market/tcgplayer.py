from market.models import MarketResult


class TCGPlayerProvider:

    name = "tcgplayer"

    def search(self, item):

        return MarketResult(
            provider="TCGPlayer",
            average_price=None,
            lowest_price=None,
            highest_price=None,
            sold_count=None,
            confidence="UNKNOWN",
            notes="TCGPlayer integration not connected yet.",
        )