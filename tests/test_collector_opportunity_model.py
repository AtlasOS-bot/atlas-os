import pytest

from collector_intelligence.enums import (
    AcquisitionDifficulty,
    DemandDirection,
    PrimaryStrategy,
    Recommendation,
    SourceType,
)
from collector_intelligence.models import (
    CollectorOpportunity,
)
from collector_intelligence.normalize import (
    compute_dedup_key,
    normalize_text,
)
from collector_intelligence.summary import (
    summarize_opportunity,
)


# ---------------------------------------------------------------
# 1. A normal limited-edition collectible
# ---------------------------------------------------------------

def test_normal_limited_edition_collectible():
    opportunity = CollectorOpportunity(
        product_name="Squishmallow 16in Autumn Fox",
        brand="Squishmallows",
        franchise="Squishmallows",
        category="Plush",
        retail_price=24.99,
        currency="USD",
        retailer="Target",
        limited_quantity=True,
        stated_quantity=5000,
        numbered=False,
        acquisition_difficulty=(
            AcquisitionDifficulty.MODERATE
        ),
        current_market_price=45.00,
        demand_direction=DemandDirection.RISING,
        collector_score=62,
        flip_score=55,
        hold_score=48,
        recommendation=Recommendation.BUY,
        primary_strategy=PrimaryStrategy.QUICK_FLIP,
    )

    assert opportunity.opportunity_id is not None
    assert opportunity.dedup_key
    assert opportunity.normalized_product_name == (
        "squishmallow 16in autumn fox"
    )
    assert opportunity.estimated_profit == (
        45.00 - 24.99
    )
    assert opportunity.recommendation == "BUY"
    assert (
        opportunity.primary_strategy
        == "QUICK_FLIP"
    )


# ---------------------------------------------------------------
# 2. A collaboration promo
# ---------------------------------------------------------------

def test_collaboration_promo():
    opportunity = CollectorOpportunity(
        product_name=(
            "One Piece x Round1 Promo Pack"
        ),
        brand="One Piece",
        franchise="One Piece",
        collaboration_partner="Round1",
        category="Trading Card",
        required_spend=200.0,
        currency="USD",
        retailer="Round1",
        first_collaboration=True,
        exclusive_promo=True,
        event_attendance_required=True,
        acquisition_difficulty=(
            AcquisitionDifficulty.HARD
        ),
        recent_sold_price=2200.0,
        demand_direction=DemandDirection.SURGING,
        collector_score=90,
        flip_score=92,
        recommendation=(
            Recommendation.CRITICAL_BUY
        ),
        primary_strategy=(
            PrimaryStrategy.QUICK_FLIP
        ),
    )

    assert opportunity.collaboration_partner == (
        "Round1"
    )
    assert opportunity.exclusive_promo is True
    assert opportunity.estimated_profit == 2000.0


# ---------------------------------------------------------------
# 3. A product with no resale data
# ---------------------------------------------------------------

def test_product_with_no_resale_data():
    opportunity = CollectorOpportunity(
        product_name="LEGO Botanical Bonsai Tree",
        brand="LEGO",
        retail_price=49.99,
    )

    assert opportunity.current_market_price is None
    assert opportunity.recent_sold_price is None
    assert (
        opportunity.estimated_market_price is None
    )
    assert opportunity.resolved_resale() == (
        None,
        None,
    )
    # No resale figure known -> no invented profit either.
    assert opportunity.estimated_profit is None
    assert (
        opportunity.estimated_roi_percent is None
    )


# ---------------------------------------------------------------
# 4. A rumored product
# ---------------------------------------------------------------

def test_rumored_product():
    opportunity = CollectorOpportunity(
        product_name=(
            "Pop Mart x Sanrio Blind Box "
            "(unconfirmed)"
        ),
        brand="Pop Mart",
        collaboration_partner="Sanrio",
        status="Rumored",
        source_type=SourceType.SOCIAL,
        source_confidence="LOW",
    )

    assert opportunity.status == "rumored"
    assert opportunity.collector_score is None
    assert opportunity.recommendation is None

    summary = summarize_opportunity(opportunity)
    assert (
        "(RUMORED - not yet confirmed)" in summary
    )


# ---------------------------------------------------------------
# 5. Duplicate reports from different sources
# ---------------------------------------------------------------

def test_duplicate_reports_from_different_sources_share_a_dedup_key():
    first = CollectorOpportunity(
        product_name="Funko Pop! Convention Exclusive",
        brand="Funko",
        collaboration_partner=None,
        release_date="2026-09-12",
        retailer="Funko Shop",
        source_name="Funko Newsletter",
        source_type=SourceType.OFFICIAL,
    )

    second = CollectorOpportunity(
        product_name="funko pop!  convention exclusive",
        brand="funko",
        release_date="2026-09-12T00:00:00Z",
        retailer="FUNKO SHOP",
        source_name="Reddit r/funkopop",
        source_type=SourceType.COMMUNITY,
    )

    assert first.dedup_key == second.dedup_key


def test_different_retailers_do_not_share_a_dedup_key():
    common_kwargs = dict(
        product_name="Sonny Angel Mini Figure",
        brand="Sonny Angel",
        release_date="2026-10-01",
    )

    first = CollectorOpportunity(
        **common_kwargs,
        retailer="Sonny Angel Official Store",
    )
    second = CollectorOpportunity(
        **common_kwargs,
        retailer="Target",
    )

    assert first.dedup_key != second.dedup_key


# ---------------------------------------------------------------
# 6. A high-retail-price product with weak resale potential
# ---------------------------------------------------------------

def test_high_retail_price_weak_resale_potential():
    opportunity = CollectorOpportunity(
        product_name=(
            "LEGO Star Wars UCS Millennium Falcon"
        ),
        brand="LEGO",
        retail_price=849.99,
        currency="USD",
        current_market_price=870.00,
        demand_direction=DemandDirection.FLAT,
        acquisition_difficulty=(
            AcquisitionDifficulty.EASY
        ),
        collector_score=70,
        flip_score=18,
        hold_score=60,
        recommendation=Recommendation.WATCH,
        primary_strategy=(
            PrimaryStrategy.COLLECT_ONLY
        ),
        risks=[
            "Thin margin relative to retail price",
            "Widely available at MSRP",
        ],
    )

    assert opportunity.flip_score < 30
    assert opportunity.estimated_profit == round(
        870.00 - 849.99, 2
    )
    assert (
        opportunity.primary_strategy
        == "COLLECT_ONLY"
    )


# ---------------------------------------------------------------
# 7. A low-cost promotional item with strong resale potential
# ---------------------------------------------------------------

def test_low_cost_promo_strong_resale_potential():
    opportunity = CollectorOpportunity(
        product_name=(
            "Starbucks Anniversary Tumbler Promo"
        ),
        brand="Starbucks",
        required_spend=15.0,
        currency="USD",
        retailer="Starbucks",
        exclusive_promo=True,
        limited_quantity=True,
        recent_sold_price=180.0,
        demand_direction=DemandDirection.SURGING,
        acquisition_difficulty=(
            AcquisitionDifficulty.MODERATE
        ),
        collector_score=80,
        flip_score=94,
        recommendation=(
            Recommendation.STRONG_BUY
        ),
        primary_strategy=(
            PrimaryStrategy.FLIP_NOW
        ),
    )

    assert opportunity.flip_score > 90
    assert opportunity.estimated_profit == 165.0
    assert opportunity.estimated_roi_percent == (
        1100.0
    )


# ---------------------------------------------------------------
# 8. One Piece x Round1-style opportunity (full fixture)
# ---------------------------------------------------------------

def make_one_piece_round1_fixture():
    return CollectorOpportunity(
        product_name=(
            "One Piece TCG x Round1 Promo Pack"
        ),
        brand="One Piece",
        franchise="One Piece",
        product_line="One Piece Card Game",
        category="Trading Card",
        collaboration_partner="Round1",
        release_region="US",
        status="live",
        required_spend=200.0,
        currency="USD",
        purchase_method=(
            "In-arcade redemption after "
            "qualifying spend"
        ),
        retailer="Round1",
        event_attendance_required=True,
        bundle_required=True,
        online_available=False,
        in_store_available=True,
        first_collaboration=True,
        exclusive_promo=True,
        exclusive_artwork=True,
        event_exclusive=True,
        acquisition_difficulty=(
            AcquisitionDifficulty.HARD
        ),
        set_or_series="Round1 Collaboration Promos",
        sealed_product=True,
        recent_sold_price=2200.0,
        demand_direction=DemandDirection.SURGING,
        sales_velocity=None,
        collector_score=96,
        flip_score=98,
        hold_score=82,
        scarcity_score=88,
        demand_score=95,
        hype_score=97,
        acquisition_score=40,
        risk_score=35,
        confidence_score=70,
        recommendation=(
            Recommendation.CRITICAL_BUY
        ),
        primary_strategy=(
            PrimaryStrategy.QUICK_FLIP
        ),
        flip_time_horizon="1-3 weeks",
        reasoning=[
            (
                "Major franchise collaboration with "
                "an arcade chain"
            ),
            "Promotional packs not sold at retail",
        ],
        risks=[
            (
                "Resale figures may reflect complete "
                "sets, not a single pack"
            ),
            "Prices may decline after initial hype",
            (
                "Acquisition requirements may vary "
                "by location"
            ),
        ],
        catalyst_signals=[
            "Major franchise collaboration",
            "Exclusive promotional packs",
            "High acquisition barrier",
            "Rapid collector demand",
            "Limited availability",
        ],
        source_name="Community report",
        source_type=SourceType.COMMUNITY,
        source_confidence="MEDIUM",
    )


def test_one_piece_round1_fixture_required_spend_and_resale():
    opportunity = make_one_piece_round1_fixture()

    assert opportunity.required_spend == 200.0
    assert opportunity.recent_sold_price == 2200.0
    assert opportunity.estimated_profit == 2000.0


def test_one_piece_round1_fixture_promo_and_collaboration_flags():
    opportunity = make_one_piece_round1_fixture()

    assert opportunity.exclusive_promo is True
    assert opportunity.first_collaboration is True
    assert (
        opportunity.collaboration_partner
        == "Round1"
    )


def test_one_piece_round1_fixture_scores():
    opportunity = make_one_piece_round1_fixture()

    assert opportunity.flip_score >= 90
    assert opportunity.collector_score >= 90


def test_one_piece_round1_fixture_carries_complete_set_risk_warning():
    opportunity = make_one_piece_round1_fixture()

    assert any(
        "complete set" in risk.lower()
        for risk in opportunity.risks
    )


def test_one_piece_round1_fixture_summary_matches_expected_format():
    opportunity = make_one_piece_round1_fixture()

    summary = summarize_opportunity(opportunity)

    assert (
        "ONE PIECE × ROUND1 PROMO" in summary
    )
    assert "CRITICAL BUY" in summary
    assert "QUICK FLIP" in summary
    assert "$200" in summary
    assert "$2,200" in summary
    assert "$2,000" in summary
    assert "96/100" in summary
    assert "98/100" in summary
    assert "82/100" in summary
    assert (
        "Major franchise collaboration" in summary
    )
    assert (
        "complete sets" in summary
        or "complete set" in summary
    )


# ---------------------------------------------------------------
# Validation and safe defaults
# ---------------------------------------------------------------

def test_score_out_of_range_raises():
    with pytest.raises(ValueError):
        CollectorOpportunity(
            product_name="Bad Score Item",
            brand="Test",
            collector_score=150,
        )


def test_negative_score_raises():
    with pytest.raises(ValueError):
        CollectorOpportunity(
            product_name="Bad Score Item",
            brand="Test",
            flip_score=-1,
        )


def test_invalid_enum_value_raises():
    with pytest.raises(ValueError):
        CollectorOpportunity(
            product_name="Bad Enum Item",
            brand="Test",
            recommendation="SUPER_MEGA_BUY",
        )


def test_enum_field_accepts_lowercase_string():
    opportunity = CollectorOpportunity(
        product_name="Case Insensitive Item",
        brand="Test",
        recommendation="buy",
    )

    assert opportunity.recommendation == "BUY"


def test_default_construction_leaves_scores_and_market_data_unknown():
    opportunity = CollectorOpportunity(
        product_name="Bare Minimum Item",
        brand="Test",
    )

    assert opportunity.collector_score is None
    assert opportunity.flip_score is None
    assert opportunity.current_market_price is None
    assert opportunity.recent_sold_price is None
    assert opportunity.limited_quantity is False
    assert opportunity.character_names == []
    assert opportunity.evidence == []


def test_discovered_at_and_ids_are_auto_populated():
    opportunity = CollectorOpportunity(
        product_name="Auto Fields Item",
        brand="Test",
    )

    assert opportunity.discovered_at is not None
    assert opportunity.opportunity_id is not None
    assert opportunity.dedup_key is not None


def test_explicit_ids_are_not_overwritten():
    opportunity = CollectorOpportunity(
        product_name="Explicit Id Item",
        brand="Test",
        opportunity_id="explicit-id-123",
        dedup_key="explicit-dedup-key",
    )

    assert (
        opportunity.opportunity_id
        == "explicit-id-123"
    )
    assert (
        opportunity.dedup_key
        == "explicit-dedup-key"
    )


# ---------------------------------------------------------------
# normalize.py
# ---------------------------------------------------------------

def test_normalize_text_strips_case_and_punctuation():
    assert normalize_text(
        "  Funko Pop!  Convention-Exclusive "
    ) == "funko pop convention exclusive"


def test_normalize_text_handles_none_and_empty():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


def test_compute_dedup_key_is_deterministic():
    key_a = compute_dedup_key(
        brand="Funko",
        franchise=None,
        product_name="Pop! Exclusive",
        collaboration_partner=None,
        release_date="2026-09-12",
        retailer="Funko Shop",
    )

    key_b = compute_dedup_key(
        brand="Funko",
        franchise=None,
        product_name="Pop! Exclusive",
        collaboration_partner=None,
        release_date="2026-09-12",
        retailer="Funko Shop",
    )

    assert key_a == key_b


# ---------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------

def test_to_dict_and_from_dict_round_trip():
    original = make_one_piece_round1_fixture()

    as_dict = original.to_dict()
    rebuilt = CollectorOpportunity.from_dict(
        as_dict
    )

    assert rebuilt.dedup_key == original.dedup_key
    assert (
        rebuilt.opportunity_id
        == original.opportunity_id
    )
    assert (
        rebuilt.estimated_profit
        == original.estimated_profit
    )


def test_from_dict_ignores_unknown_keys():
    data = {
        "product_name": "Ignore Extra Keys Item",
        "brand": "Test",
        "some_future_field_not_yet_modeled": True,
    }

    opportunity = CollectorOpportunity.from_dict(
        data
    )

    assert (
        opportunity.product_name
        == "Ignore Extra Keys Item"
    )


# ---------------------------------------------------------------
# Summary: confirmed vs. estimated vs. missing
# ---------------------------------------------------------------

def test_summary_labels_estimated_resale_distinctly_from_observed():
    estimated_only = CollectorOpportunity(
        product_name="Estimate Only Item",
        brand="Test",
        required_spend=50.0,
        estimated_market_price=120.0,
    )

    summary = summarize_opportunity(
        estimated_only
    )

    assert "(estimated)" in summary


def test_summary_shows_unknown_for_missing_scores_and_prices():
    bare = CollectorOpportunity(
        product_name="Nothing Known Item",
        brand="Test",
    )

    summary = summarize_opportunity(bare)

    assert "Unknown" in summary
    assert "Missing information:" in summary
