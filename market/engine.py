from market import ALL_MARKET_PROVIDERS
from market.aggregator import MarketAggregator
from market.cache import market_cache
from market.router import MarketRouter


class MarketEngine:

    @staticmethod
    def research(item):

        cache_key = (
            item.get("brand", "")
            + "|"
            + item.get("title", "")
        )

        cached = market_cache.get(cache_key)

        if cached is not None:
            return cached

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

        result = {
            "summary": MarketAggregator.aggregate(
                provider_results
            ),
            "providers": provider_results,
        }

        market_cache.set(cache_key, result)

        return result