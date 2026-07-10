from market.models import MarketResult
from market.provider import MarketProvider


class ManualMarketProvider(MarketProvider):
    name = "manual"

    def search(self, item):
        market_data = item.get("manual_market")

        if not market_data:
            return MarketResult(
                provider="Manual",
                average_price=None,
                lowest_price=None,
                highest_price=None,
                sold_count=None,
                confidence="NO_DATA",
                notes="No manual market data supplied.",
            )

        return MarketResult(
            provider="Manual",
            average_price=market_data.get("average_price"),
            lowest_price=market_data.get("lowest_price"),
            highest_price=market_data.get("highest_price"),
            sold_count=market_data.get("sold_count"),
            last_sale_price=market_data.get("last_sale_price"),
            last_sale_date=market_data.get("last_sale_date"),
            confidence=market_data.get("confidence", "MEDIUM"),
            notes=market_data.get(
                "notes",
                "Market figures entered manually.",
            ),
        )