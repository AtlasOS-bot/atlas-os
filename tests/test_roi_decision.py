from decision.decision_engine import decide


def test_high_roi_can_produce_buy():
    roi = {
        "profit": 40.00,
        "roi": 80.00,
    }

    result = decide(
        score=80,
        reprint_risk=False,
        pattern_count=2,
        roi=roi,
    )

    assert result["action"] == "BUY"


def test_negative_profit_produces_skip():
    roi = {
        "profit": -5.00,
        "roi": -10.00,
    }

    result = decide(
        score=90,
        reprint_risk=False,
        pattern_count=3,
        roi=roi,
    )

    assert result["action"] == "SKIP"


def test_reprint_risk_prevents_immediate_buy():
    roi = {
        "profit": 50.00,
        "roi": 90.00,
    }

    result = decide(
        score=90,
        reprint_risk=True,
        pattern_count=3,
        roi=roi,
    )

    assert result["action"] == "WATCH"