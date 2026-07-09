from market import ALL_MARKET_PROVIDERS
from market.aggregator import MarketAggregator
from market.router import MarketRouter


class MarketEngine:

    @staticmethod
    def research(item):

        selected_providers = MarketRouter.providers_for(
            item,
            ALL_MARKET_PROVIDERS,
        )

        provider_results = []

        for provider in selected_providers:

            if provider is None:
                continue

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