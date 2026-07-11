from signals.investment_strategy import (
    InvestmentStrategySignal,
)


def test_high_strategy_score_fires_signal():
    signal = (
        InvestmentStrategySignal()
    )

    item = {
        "best_strategy": {
            "strategy": (
                "LONG-TERM HOLD"
            ),
            "score": 88,
        }
    }

    result = signal.evaluate(item)

    assert result.detected is True
    assert result.weight == 14


def test_low_strategy_score_does_not_fire():
    signal = (
        InvestmentStrategySignal()
    )

    item = {
        "best_strategy": {
            "strategy": (
                "SLEEPER WATCH"
            ),
            "score": 30,
        }
    }

    result = signal.evaluate(item)

    assert result.detected is False
    assert result.weight == 0