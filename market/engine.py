from market import ALL_MARKET_PROVIDERS
from market.aggregator import MarketAggregator


class MarketEngine:

    @staticmethod
    def research(item):

        provider_results = []

        for provider in ALL_MARKET_PROVIDERS:

            provider_results.append(
                provider.search(item)
            )

        summary = MarketAggregator.aggregate(
            provider_results
        )

        return {
            "summary": summary,
            "providers": provider_results,
        }