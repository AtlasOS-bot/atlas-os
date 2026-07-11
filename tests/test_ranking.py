from atlas.ranking import OpportunityRanker


def test_buy_with_high_roi_ranks_first():
    opportunities = [
        {
            "item": {"title": "Watch Item"},
            "analysis": {
                "decision": "WATCH",
                "confidence": "HIGH",
                "urgency": "HIGH",
                "score": 90,
                "roi": {
                    "profit": 20,
                    "roi": 30,
                },
            },
        },
        {
            "item": {"title": "Best Buy Item"},
            "analysis": {
                "decision": "BUY",
                "confidence": "HIGH",
                "urgency": "MEDIUM",
                "score": 80,
                "roi": {
                    "profit": 50,
                    "roi": 85,
                },
            },
        },
        {
            "item": {"title": "Lower ROI Buy"},
            "analysis": {
                "decision": "BUY",
                "confidence": "VERY HIGH",
                "urgency": "VERY HIGH",
                "score": 95,
                "roi": {
                    "profit": 25,
                    "roi": 45,
                },
            },
        },
    ]

    ranked = OpportunityRanker.rank(opportunities)

    assert ranked[0]["item"]["title"] == "Best Buy Item"
    assert ranked[1]["item"]["title"] == "Lower ROI Buy"
    assert ranked[2]["item"]["title"] == "Watch Item"


def test_skip_ranks_last():
    opportunities = [
        {
            "item": {"title": "Skip Item"},
            "analysis": {
                "decision": "SKIP",
                "confidence": "HIGH",
                "urgency": "HIGH",
                "score": 95,
                "roi": {
                    "profit": -5,
                    "roi": -10,
                },
            },
        },
        {
            "item": {"title": "Watch Item"},
            "analysis": {
                "decision": "WATCH",
                "confidence": "LOW",
                "urgency": "LOW",
                "score": 50,
                "roi": None,
            },
        },
    ]

    ranked = OpportunityRanker.rank(opportunities)

    assert ranked[-1]["item"]["title"] == "Skip Item"