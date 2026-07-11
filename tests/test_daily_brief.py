from atlas.daily_brief import DailyBrief


def test_daily_brief_ranks_buy_before_watch():
    opportunities = [
        {
            "item": {
                "title": "Watch Product",
                "brand": "Pokemon",
            },
            "analysis": {
                "decision": "WATCH",
                "confidence": "MEDIUM",
                "opportunity": "MEDIUM",
                "urgency": "LOW",
                "score": 65,
                "market": {"summary": {}},
                "roi": None,
                "reasons": ["More evidence is needed."],
            },
        },
        {
            "item": {
                "title": "Buy Product",
                "brand": "Nike",
            },
            "analysis": {
                "decision": "BUY",
                "confidence": "HIGH",
                "opportunity": "HIGH",
                "urgency": "HIGH",
                "score": 85,
                "market": {
                    "summary": {
                        "average_price": 120,
                        "sold_count": 20,
                        "confidence": "HIGH",
                    }
                },
                "roi": {
                    "retail_price": 60,
                    "average_sold_price": 120,
                    "fees": 15.60,
                    "shipping": 8,
                    "net_revenue": 96.40,
                    "profit": 36.40,
                    "roi": 60.67,
                },
                "reasons": ["Strong resale opportunity."],
            },
        },
    ]

    brief = DailyBrief.generate(opportunities)

    assert brief.index("Buy Product") < brief.index("Watch Product")
    assert "#1" in brief
    assert "#2" in brief