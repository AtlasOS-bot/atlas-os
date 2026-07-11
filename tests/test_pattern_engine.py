from patterns.engine import PatternEngine
from patterns.history import PATTERN_HISTORY


def test_pattern_engine():
    original_history = PATTERN_HISTORY.copy()

    try:
        PATTERN_HISTORY.clear()

        PATTERN_HISTORY["pokemon_plush"] = {
            "keywords": ["pikachu"],
            "category": "pokemon",
            "historical_roi": 82,
        }

        item = {
            "title": "Professor Willow Pikachu Plush",
            "category": "pokemon",
        }

        result = PatternEngine.analyze(item)

        assert result["summary"]["pattern_score"] == 82
        assert result["summary"]["confidence"] == "VERY HIGH"

    finally:
        PATTERN_HISTORY.clear()
        PATTERN_HISTORY.update(original_history)