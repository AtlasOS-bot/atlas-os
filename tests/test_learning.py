from learning.engine import LearningEngine
from learning.storage import JsonLearningStore


def test_learning_engine_records_analysis(tmp_path):
    history_path = (
        tmp_path
        / "learning_history.json"
    )

    store = JsonLearningStore(
        path=history_path
    )

    engine = LearningEngine(
        store=store
    )

    item = {
        "title": "Test Pikachu Plush",
        "brand": "Pokemon",
        "category": "pokemon",
        "url": "https://example.com/pikachu",
        "retail_price": 40.00,
    }

    analysis = {
        "decision": "BUY",
        "score": 85,
        "confidence": "HIGH",
        "opportunity": "HIGH",
        "urgency": "MEDIUM",
        "market": {
            "summary": {
                "average_price": 90.00,
            }
        },
        "roi": {
            "profit": 30.00,
            "roi": 75.00,
        },
        "patterns": {
            "summary": {
                "pattern_score": 80,
                "confidence": "VERY HIGH",
            },
            "matches": [
                {
                    "name": "pokemon_plush",
                }
            ],
        },
        "evidence": [
            {
                "type": "exclusive",
                "signal": "exclusive",
                "weight": 10,
                "reason": (
                    "Exclusive product language detected."
                ),
            }
        ],
    }

    record = engine.record(
        item=item,
        analysis=analysis,
    )

    saved_records = store.all()

    assert len(saved_records) == 1
    assert record["title"] == "Test Pikachu Plush"
    assert record["decision"] == "BUY"
    assert record["estimated_roi"] == 75.00
    assert record["pattern_names"] == [
        "pokemon_plush"
    ]