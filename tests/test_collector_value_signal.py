from signals.collector_value import (
    CollectorValueSignal,
)


def test_collector_value_signal_uses_dynamic_weight():
    signal = CollectorValueSignal()

    item = {
        "collector_score": 90,
        "collector_level": "ELITE",
    }

    result = signal.evaluate(item)

    assert result.detected is True
    assert result.weight == 16
    assert result.signal == "collector_value"


def test_low_collector_score_does_not_fire():
    signal = CollectorValueSignal()

    item = {
        "collector_score": 20,
        "collector_level": "LOW",
    }

    result = signal.evaluate(item)

    assert result.detected is False
    assert result.weight == 0