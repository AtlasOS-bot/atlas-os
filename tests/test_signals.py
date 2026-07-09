from signals import ALL_SIGNALS


def test_signal_registry():

    assert len(ALL_SIGNALS) > 0

    names = []

    for signal in ALL_SIGNALS:

        names.append(signal.name)

    assert "official_source" in names
    assert "limited_release" in names
    assert "exclusive" in names
    assert "collaboration" in names
    assert "shock_drop" in names
    assert "restock" in names
    assert "reprint" in names