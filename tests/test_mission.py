from atlas.mission import MissionBrief


def test_mission():

    item = {
        "title": "Test Item",
        "brand": "Pokemon",
    }

    analysis = {
        "decision": "BUY",
        "confidence": "HIGH",
        "reasons": [
            "Official release",
            "Collector demand",
        ],
    }

    text = MissionBrief.generate(item, analysis)

    assert "BUY" in text
    assert "Collector demand" in text