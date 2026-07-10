class MarketRouter:

    @staticmethod
    def providers_for(item, providers):
        category = (item.get("category") or "").lower()
        title = (item.get("title") or "").lower()
        brand = (item.get("brand") or "").lower()

        provider_map = {
            provider.name: provider
            for provider in providers
        }

        selected = []

        # Always check for manually supplied market figures first.
        if provider_map.get("manual"):
            selected.append(provider_map["manual"])

        if (
            category in ["pokemon", "tcg"]
            or "pokemon" in brand
            or "pokémon" in title
        ):
            selected.extend([
                provider_map.get("tcgplayer"),
                provider_map.get("pricecharting"),
                provider_map.get("ebay"),
            ])

        elif (
            category == "nike"
            or "nike" in brand
            or "snkrs" in title
        ):
            selected.extend([
                provider_map.get("stockx"),
                provider_map.get("ebay"),
            ])

        else:
            selected.append(provider_map.get("ebay"))

        return [
            provider
            for provider in selected
            if provider is not None
        ]