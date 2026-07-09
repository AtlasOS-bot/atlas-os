import urllib.parse

from market.models import MarketResult
from market.provider import MarketProvider


class EbayProvider(MarketProvider):
    name = "ebay"

    def search(self, item):
        title = item.get("title", "")
        query = urllib.parse.quote_plus(title)

        sold_url = (
            "https://www.ebay.com/sch/i.html"
            f"?_nkw={query}&LH_Sold=1&LH_Complete=1"
        )

        return MarketResult(
            provider="eBay",
            average_price=None,
            lowest_price=None,
            highest_price=None,
            sold_count=None,
            confidence="LINK_ONLY",
            notes=f"Manual eBay sold-comps link created: {sold_url}",
        )