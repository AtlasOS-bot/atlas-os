class MarketRouter:

    @staticmethod
    def providers_for(item, providers):
        category = (item.get("category") or "").lower()
        title = (item.get("title") or "").lower()
        brand = (item.get("brand") or "").lower()

        provider_map = {provider.name: provider for provider in providers}

        if category in ["pokemon", "tcg"] or "pokemon" in brand or "pokémon" in title:
            return [
                provider_map.get("tcgplayer"),
                provider_map.get("pricecharting"),
                provider_map.get("ebay"),
            ]

        if category == "nike" or "nike" in brand or "snkrs" in title:
            return [
                provider_map.get("stockx"),
                provider_map.get("ebay"),
            ]

        return [
            provider_map.get("ebay"),
        ]