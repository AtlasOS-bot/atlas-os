from learning.statistics import LearningStatistics


def test_learning_statistics_calculates_category_summary():
    records = [
        {
            "category": "pokemon",
            "brand": "Pokemon",
            "decision": "BUY",
            "score": 85,
            "estimated_roi": 80,
            "estimated_profit": 40,
            "average_market_price": 100,
        },
        {
            "category": "pokemon",
            "brand": "Pokemon",
            "decision": "WATCH",
            "score": 65,
            "estimated_roi": 40,
            "estimated_profit": 20,
            "average_market_price": 80,
        },
        {
            "category": "pokemon",
            "brand": "Pokemon",
            "decision": "SKIP",
            "score": 45,
            "estimated_roi": -10,
            "estimated_profit": -5,
            "average_market_price": 50,
        },
    ]

    summaries = LearningStatistics.summarize(
        records
    )

    pokemon = summaries["pokemon:Pokemon"]

    assert pokemon["total_records"] == 3
    assert pokemon["average_roi"] == 36.67
    assert pokemon["average_profit"] == 18.33
    assert pokemon["average_market_price"] == 76.67
    assert pokemon["profitable_count"] == 2
    assert pokemon["buy_count"] == 1
    assert pokemon["skip_count"] == 1
    assert pokemon["confidence"] == "LOW"


def test_learning_statistics_separates_brands():
    records = [
        {
            "category": "pokemon",
            "brand": "Pokemon",
            "decision": "BUY",
            "score": 80,
            "estimated_roi": 70,
            "estimated_profit": 35,
        },
        {
            "category": "nike",
            "brand": "Nike",
            "decision": "WATCH",
            "score": 60,
            "estimated_roi": 20,
            "estimated_profit": 10,
        },
    ]

    summaries = LearningStatistics.summarize(
        records
    )

    assert "pokemon:Pokemon" in summaries
    assert "nike:Nike" in summaries
    assert summaries["pokemon:Pokemon"]["average_roi"] == 70
    assert summaries["nike:Nike"]["average_roi"] == 20