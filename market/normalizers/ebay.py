from market.models import MarketResult


def normalize_ebay(raw_data):

    if raw_data is None:

        return MarketResult(
            provider="eBay",
            average_price=None,
            lowest_price=None,
            highest_price=None,
            sold_count=None,
            confidence="NO_DATA",
            notes="No eBay data available.",
        )

    return MarketResult(
        provider="eBay",
        average_price=raw_data.get("average_price"),
        lowest_price=raw_data.get("lowest_price"),
        highest_price=raw_data.get("highest_price"),
        sold_count=raw_data.get("sold_count"),
        confidence=raw_data.get("confidence", "UNKNOWN"),
        notes=raw_data.get("notes", ""),
    )