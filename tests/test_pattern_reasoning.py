from brain.atlas_brain import AtlasBrain
from patterns.history import PATTERN_HISTORY


def test_pattern_match_flows_into_reasoning():
    original_history = PATTERN_HISTORY.copy()

    try:
        PATTERN_HISTORY.clear()

        PATTERN_HISTORY["test_pikachu_pattern"] = {
            "keywords": ["pikachu", "plush"],
            "category": "pokemon",
            "historical_roi": 80,
        }

        item = {
            "title": "Limited Pikachu Plush",
            "description": "Exclusive collector release",
            "brand": "Pokemon",
            "category": "pokemon",
            "url": "https://example.com/pikachu",
        }

        analysis = AtlasBrain.analyze(
            item=item,
            category="pokemon",
        )

        assert analysis["patterns"]["summary"]["pattern_score"] == 80
        assert analysis["patterns"]["summary"]["confidence"] == "VERY HIGH"

        evidence_types = [
            evidence["type"]
            for evidence in analysis["evidence"]
        ]

        assert "historical_pattern_match" in evidence_types

    finally:
        PATTERN_HISTORY.clear()
        PATTERN_HISTORY.update(original_history)


def test_unmatched_item_has_no_pattern_evidence():
    original_history = PATTERN_HISTORY.copy()

    try:
        PATTERN_HISTORY.clear()

        item = {
            "title": "Unknown Product",
            "description": "",
            "brand": "Unknown",
            "category": "unknown",
            "url": "https://example.com/unknown",
        }

        analysis = AtlasBrain.analyze(
            item=item,
            category="unknown",
        )

        evidence_types = [
            evidence["type"]
            for evidence in analysis["evidence"]
        ]

        assert "historical_pattern_match" not in evidence_types

    finally:
        PATTERN_HISTORY.clear()
        PATTERN_HISTORY.update(original_history)