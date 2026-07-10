from atlas.mission import MissionBrief
from brain.atlas_brain import AtlasBrain


def test_market_data_flows_into_roi_and_mission():
    item = {
        "title": "Atlas ROI Integration Test Product",
        "brand": "Pokemon",
        "category": "pokemon",
        "description": "Limited exclusive collector product",
        "url": "https://example.com/test-product",
        "retail_price": 50.00,
        "manual_market": {
            "average_price": 110.00,
            "lowest_price": 95.00,
            "highest_price": 135.00,
            "sold_count": 25,
            "confidence": "HIGH",
        },
    }

    analysis = AtlasBrain.analyze(
        item=item,
        category="pokemon",
    )

    assert analysis["market"]["summary"]["average_price"] == 110.00
    assert analysis["roi"] is not None
    assert analysis["roi"]["profit"] > 0
    assert analysis["roi"]["roi"] > 50

    brief = MissionBrief.generate(item, analysis)

    assert "MARKET INTELLIGENCE" in brief
    assert "ROI ANALYSIS" in brief
    assert "$110.00" in brief