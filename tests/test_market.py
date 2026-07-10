from market.engine import MarketEngine


def test_manual_market_data():

    item = {
        "title": "Test Pokemon Product",
        "brand": "Pokemon",
        "category": "pokemon",
        "manual_market": {
            "average_price": 110.00,
            "lowest_price": 95.00,
            "highest_price": 135.00,
            "sold_count": 25,
            "confidence": "HIGH",
        },
    }

    market = MarketEngine.research(item)
    summary = market["summary"]

    assert summary["providers_with_data"] >= 1
    assert summary["average_price"] == 110.00
    assert summary["sold_count"] == 25