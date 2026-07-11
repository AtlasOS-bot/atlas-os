from collections import defaultdict
from statistics import mean


class LearningStatistics:

    @staticmethod
    def summarize(records):
        groups = defaultdict(list)

        for record in records:
            category = record.get("category") or "general"
            brand = record.get("brand") or "Unknown"

            group_key = f"{category}:{brand}"
            groups[group_key].append(record)

        summaries = {}

        for group_key, group_records in groups.items():
            summaries[group_key] = (
                LearningStatistics._summarize_group(
                    group_records
                )
            )

        return summaries

    @staticmethod
    def _summarize_group(records):
        roi_values = [
            record["estimated_roi"]
            for record in records
            if record.get("estimated_roi") is not None
        ]

        profit_values = [
            record["estimated_profit"]
            for record in records
            if record.get("estimated_profit") is not None
        ]

        market_prices = [
            record["average_market_price"]
            for record in records
            if record.get("average_market_price") is not None
        ]

        scores = [
            record.get("score", 0)
            for record in records
        ]

        decisions = [
            record.get("decision", "WATCH")
            for record in records
        ]

        buy_count = decisions.count("BUY")
        strong_watch_count = decisions.count("STRONG WATCH")
        watch_count = decisions.count("WATCH")
        skip_count = decisions.count("SKIP")

        total_records = len(records)

        profitable_count = len([
            profit
            for profit in profit_values
            if profit > 0
        ])

        average_roi = (
            round(mean(roi_values), 2)
            if roi_values
            else None
        )

        average_profit = (
            round(mean(profit_values), 2)
            if profit_values
            else None
        )

        average_market_price = (
            round(mean(market_prices), 2)
            if market_prices
            else None
        )

        average_score = (
            round(mean(scores), 2)
            if scores
            else 0
        )

        profitable_rate = (
            round(
                profitable_count
                / len(profit_values)
                * 100,
                2,
            )
            if profit_values
            else None
        )

        buy_rate = (
            round(
                buy_count
                / total_records
                * 100,
                2,
            )
            if total_records
            else 0
        )

        return {
            "total_records": total_records,
            "records_with_roi": len(roi_values),
            "records_with_profit": len(profit_values),

            "average_roi": average_roi,
            "average_profit": average_profit,
            "average_market_price": average_market_price,
            "average_score": average_score,

            "profitable_count": profitable_count,
            "profitable_rate": profitable_rate,

            "buy_count": buy_count,
            "strong_watch_count": strong_watch_count,
            "watch_count": watch_count,
            "skip_count": skip_count,
            "buy_rate": buy_rate,

            "confidence": (
                LearningStatistics._confidence(
                    total_records
                )
            ),
        }

    @staticmethod
    def _confidence(total_records):
        if total_records >= 25:
            return "VERY HIGH"

        if total_records >= 10:
            return "HIGH"

        if total_records >= 5:
            return "MEDIUM"

        return "LOW"