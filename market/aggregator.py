class MarketAggregator:

    @staticmethod
    def aggregate(results):

        valid = [
            r
            for r in results
            if r.average_price is not None
        ]

        if not valid:

            return {
                "providers": len(results),
                "providers_with_data": 0,
                "average_price": None,
                "lowest_price": None,
                "highest_price": None,
                "sold_count": 0,
                "confidence": "UNKNOWN",
            }

        averages = [r.average_price for r in valid]

        lows = [
            r.lowest_price
            for r in valid
            if r.lowest_price is not None
        ]

        highs = [
            r.highest_price
            for r in valid
            if r.highest_price is not None
        ]

        sold = [
            r.sold_count
            for r in valid
            if r.sold_count is not None
        ]

        return {
            "providers": len(results),
            "providers_with_data": len(valid),
            "average_price": round(sum(averages) / len(averages), 2),
            "lowest_price": min(lows) if lows else None,
            "highest_price": max(highs) if highs else None,
            "sold_count": sum(sold),
            "confidence": "HIGH" if len(valid) >= 2 else "MEDIUM",
        }