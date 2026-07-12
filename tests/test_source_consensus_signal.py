from signals.source_consensus import (
    SourceConsensusSignal,
)


def test_high_consensus_fires_signal():
    signal = SourceConsensusSignal()

    item = {
        "consensus_score": 88,
        "confirmation_count": 3,
    }

    result = signal.evaluate(item)

    assert result.detected is True
    assert result.weight == 14


def test_low_consensus_does_not_fire():
    signal = SourceConsensusSignal()

    item = {
        "consensus_score": 25,
        "confirmation_count": 1,
    }

    result = signal.evaluate(item)

    assert result.detected is False
    assert result.weight == 0