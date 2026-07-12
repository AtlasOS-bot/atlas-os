from scouts.tcg.enrichment import (
    enrich_tcg_item,
)


def test_lorcana_enchanted_collection_scores_high():
    item = {
        "title": (
            "Disney Lorcana D23 "
            "Limited Collector Gift Set"
        ),
        "description": (
            "Includes exclusive promo cards "
            "and Enchanted-style artwork."
        ),
        "category": "lorcana",
        "sources": [
            "lorcana_news",
            "lorcana_products",
        ],
    }

    result = enrich_tcg_item(
        item=item,
        tcg_name="lorcana",
    )

    assert result["tcg_name"] == "lorcana"

    assert result["product_type"] in {
        "gift_set",
        "collection_set",
    }

    assert result["limited_release"] is True
    assert result["promo_included"] is True
    assert result["collector_score"] >= 70

    assert result[
        "best_strategy"
    ]["strategy"] in {
        "QUICK FLIP",
        "LONG-TERM HOLD",
    }


def test_one_piece_set_code_is_detected():
    item = {
        "title": (
            "BOOSTER PACK "
            "-ADVENTURE ON KAMI'S ISLAND- "
            "[OP15-EB04]"
        ),
        "description": (
            "Official One Piece Card Game "
            "booster product."
        ),
        "category": "one_piece",
    }

    result = enrich_tcg_item(
        item=item,
        tcg_name="one_piece",
    )

    assert result["tcg_name"] == "one_piece"

    assert "OP-15" in result["set_codes"]
    assert "EB-04" in result["set_codes"]

    assert (
        result["product_type"]
        == "booster_pack"
    )


def test_one_piece_premium_bandai_scores_high():
    item = {
        "title": (
            "ONE PIECE Premium Card "
            "Collection Anniversary Edition"
        ),
        "description": (
            "Premium Bandai limited edition "
            "with promo cards. Limit 1."
        ),
        "category": "one_piece",
        "sources": [
            "one_piece_products",
            "premium_bandai",
        ],
    }

    result = enrich_tcg_item(
        item=item,
        tcg_name="one_piece",
    )

    assert (
        result["product_type"]
        == "premium_collection"
    )

    assert result["limited_release"] is True
    assert result["promo_included"] is True
    assert result["collector_score"] >= 80
    assert result["hold_score"] >= 55


def test_basic_lorcana_accessory_scores_lower():
    item = {
        "title": (
            "Disney Lorcana Card Sleeves"
        ),
        "description": (
            "Standard card sleeves."
        ),
        "category": "lorcana",
        "sources": [
            "lorcana_products",
        ],
    }

    result = enrich_tcg_item(
        item=item,
        tcg_name="lorcana",
    )

    assert (
        result["product_type"]
        == "accessory"
    )

    assert result["collector_score"] < 55