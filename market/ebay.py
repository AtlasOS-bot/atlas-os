import urllib.parse

from market.ebay_live import fetch_ebay_sold_data
from market.normalizers.ebay import normalize_ebay
from market.provider import MarketProvider


class EbayProvider(MarketProvider):

    name = "ebay"

    def search(self, item):

        raw = fetch_ebay_sold_data(item)

        if raw is not None:
            return normalize_ebay(raw)

        title = item.get("title", "")
        query = urllib.parse.quote_plus(title)

        sold_url = (
            "https://www.ebay.com/sch/i.html"
            f"?_nkw={query}&LH_Sold=1&LH_Complete=1"
        )

        return normalize_ebay({
            "average_price": None,
            "lowest_price": None,
            "highest_price": None,
            "sold_count": None,
            "confidence": "LINK_ONLY",
            "notes": sold_url,
        })