"""
Atlas v21 - Module 3: Collector Opportunity Scoring and Decision Engine.

Tests evaluate_opportunity() end-to-end against CollectorOpportunity
fixtures built directly (Module 1), independent of Module 2's text
extraction accuracy. Assertions favor directional/structural
properties over brittle exact-value equality, except where the
mission spec calls for a specific behavior (e.g. Fixture A/B).
"""

from collector_intelligence.decision_engine import (
    RECOMMENDATION_ORDER,
    evaluate_opportunity,
)
from collector_intelligence.enums import PrimaryStrategy, Recommendation
from collector_intelligence.models import CollectorOpportunity
from collector_intelligence.scoring_config import ScoringConfig
from collector_intelligence.scoring_models import ScoringContext


SCORE_FIELDS = [
    "collector_score",
    "flip_score",
    "hold_score",
    "scarcity_score",
    "demand_score",
    "hype_score",
    "acquisition_score",
    "risk_score",
    "confidence_score",
    "opportunity_score",
]


def make_opportunity(**overrides):
    fields = {
        "product_name": "Test Product",
        "brand": "Test Brand",
    }
    fields.update(overrides)
    return CollectorOpportunity(**fields)


# ---------------------------------------------------------------
# Required Round1 fixtures
# ---------------------------------------------------------------

def round1_fixture_a():
    return make_opportunity(
        product_name="One Piece x Round1 Exclusive Promotional Card Packs",
        brand="One Piece",
        franchise="One Piece",
        collaboration_partner="Round1",
        retailer="Round1",
        category="trading card promo",
        required_spend=200.0,
        recent_sold_price=2200.0,
        currency="USD",
        exclusive_promo=True,
        retailer_exclusive=True,
        purchase_window_start="July 20",
        purchase_window_end="August 4",
        demand_direction="RISING",
        source_type="NEWS",
        risks=[
            "This resale figure reflects a complete set of four "
            "promotional cards, not a single card."
        ],
        catalyst_signals=[
            "One Piece and Round1 launched a limited collaboration.",
            "Complete promo sets reportedly sold quickly.",
        ],
    )


def round1_fixture_b():
    return make_opportunity(
        product_name=(
            "One Piece x Round1 Verified Complete Promotional Card Set"
        ),
        brand="One Piece",
        franchise="One Piece",
        collaboration_partner="Round1",
        retailer="Round1",
        category="trading card promo",
        edition_name="Complete Set",
        required_spend=200.0,
        recent_sold_price=2200.0,
        currency="USD",
        exclusive_promo=True,
        retailer_exclusive=True,
        first_collaboration=True,
        numbered=True,
        limited_quantity=True,
        stated_quantity=100,
        purchase_limit=2,
        sellout_speed="within 30 minutes",
        demand_direction="SURGING",
        sold_listing_count=25,
        sales_velocity=10,
        purchase_window_start="July 20",
        purchase_window_end="August 4",
        online_available=True,
        status="live",
        release_date="July 20, 2026",
        source_type="OFFICIAL",
        catalyst_signals=[
            "One Piece and Round1 launched a limited collaboration.",
            "Complete sets sold out within 30 minutes.",
            "Surging resale demand reported across multiple marketplaces.",
        ],
    )


class TestRound1Fixtures:
    def test_fixture_a_flags_complete_set_mismatch(self):
        evaluation = evaluate_opportunity(round1_fixture_a())

        assert any(
            "complete set" in warning.lower()
            for warning in evaluation.warnings
        )

    def test_fixture_a_is_not_critical_buy(self):
        evaluation = evaluate_opportunity(round1_fixture_a())
        assert evaluation.recommendation != "CRITICAL_BUY"

    def test_fixture_a_risk_is_elevated(self):
        evaluation = evaluate_opportunity(round1_fixture_a())
        assert evaluation.risk_score >= 30

    def test_fixture_a_confidence_reduced_by_mismatch(self):
        mismatched = evaluate_opportunity(round1_fixture_a())

        clean = round1_fixture_a()
        clean.risks = []
        clean_eval = evaluate_opportunity(clean)

        assert mismatched.confidence_score < clean_eval.confidence_score

    def test_fixture_a_flip_score_shows_real_upside(self):
        evaluation = evaluate_opportunity(round1_fixture_a())
        assert evaluation.flip_score > 30

    def test_fixture_b_reaches_critical_buy(self):
        evaluation = evaluate_opportunity(round1_fixture_b())
        assert evaluation.recommendation == "CRITICAL_BUY"

    def test_fixture_b_has_no_complete_set_warning(self):
        evaluation = evaluate_opportunity(round1_fixture_b())
        assert not any(
            "complete set" in warning.lower()
            for warning in evaluation.warnings
        )

    def test_fixture_b_risk_lower_than_fixture_a(self):
        eval_a = evaluate_opportunity(round1_fixture_a())
        eval_b = evaluate_opportunity(round1_fixture_b())
        assert eval_b.risk_score < eval_a.risk_score

    def test_fixture_b_confidence_higher_than_fixture_a(self):
        eval_a = evaluate_opportunity(round1_fixture_a())
        eval_b = evaluate_opportunity(round1_fixture_b())
        assert eval_b.confidence_score > eval_a.confidence_score

    def test_fixture_b_respects_purchase_limit_in_quantity(self):
        evaluation = evaluate_opportunity(round1_fixture_b())
        assert evaluation.recommended_quantity <= 2


# ---------------------------------------------------------------
# Mission distinctions (items 1-10 from the spec)
# ---------------------------------------------------------------

class TestMissionDistinctions:
    def test_cheap_promo_has_asymmetric_upside(self):
        opportunity = make_opportunity(
            product_name="Cheap Promo Card",
            brand="Brand X",
            franchise="Brand X",
            required_spend=10.0,
            recent_sold_price=150.0,
            source_type="RETAILER",
            limited_quantity=True,
            purchase_limit=1,
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.flip_score > 30
        assert evaluation.estimated_roi_percent > 500

    def test_expensive_weak_collectible_scores_low(self):
        opportunity = make_opportunity(
            product_name="Expensive Weak Collectible",
            brand="Brand X",
            retail_price=870.00,
            current_market_price=890.00,
            source_type="RETAILER",
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.flip_score < 25
        assert evaluation.recommendation in {"WATCH", "SKIP", "AVOID"}

    def test_collector_only_item_favors_collect_only_strategy(self):
        opportunity = make_opportunity(
            product_name="Anniversary Exclusive Art Piece",
            brand="Brand X",
            franchise="Brand X",
            exclusive_artwork=True,
            exclusive_character=True,
            anniversary_release=True,
            first_edition=True,
            source_type="OFFICIAL",
            # Deliberately no pricing/market evidence at all.
        )
        evaluation = evaluate_opportunity(opportunity)

        assert evaluation.collector_score >= 40
        assert evaluation.recommendation in {"WATCH", "SKIP", "CONDITIONAL_BUY"}
        assert evaluation.primary_strategy in {"COLLECT_ONLY", "WATCH"}

    def test_hype_without_demand_does_not_inflate_opportunity_score(self):
        hype_only = make_opportunity(
            product_name="Hyped Collab Announcement",
            brand="Brand X",
            franchise="Brand X",
            collaboration_partner="Partner Co",
            evidence=[{"signal_type": "COMMUNITY_HYPE", "confirmed": True}],
            source_type="SOCIAL",
        )
        evaluation = evaluate_opportunity(hype_only)

        assert evaluation.hype_score >= 25
        assert evaluation.demand_score < 15
        assert evaluation.opportunity_score < 40

    def test_scarcity_with_poor_acquisition(self):
        opportunity = make_opportunity(
            product_name="Hard-to-Get Scarce Item",
            brand="Brand X",
            franchise="Brand X",
            stated_quantity=50,
            numbered=True,
            lottery_required=True,
            membership_required=True,
            event_attendance_required=True,
            required_spend=800.0,
        )
        evaluation = evaluate_opportunity(opportunity)

        assert evaluation.scarcity_score >= 40
        assert evaluation.acquisition_score < 40

    def test_rumor_stays_on_watchlist(self):
        opportunity = make_opportunity(
            product_name="Rumored Collab Set",
            brand="Brand X",
            franchise="Brand X",
            collaboration_partner="Partner Co",
            status="rumored",
            required_spend=100.0,
            recent_sold_price=800.0,
            exclusive_promo=True,
            retailer_exclusive=True,
            limited_quantity=True,
            stated_quantity=50,
            demand_direction="SURGING",
            sellout_speed="within 10 minutes",
            source_type="NEWS",
        )
        evaluation = evaluate_opportunity(opportunity)

        assert RECOMMENDATION_ORDER.index(
            evaluation.recommendation
        ) >= RECOMMENDATION_ORDER.index("WATCH")

    def test_official_release_scores_higher_confidence_than_social(self):
        base_fields = dict(
            product_name="Same Item",
            brand="Brand X",
            franchise="Brand X",
            required_spend=50.0,
            recent_sold_price=150.0,
        )
        official = evaluate_opportunity(
            make_opportunity(**base_fields, source_type="OFFICIAL")
        )
        social = evaluate_opportunity(
            make_opportunity(**base_fields, source_type="SOCIAL")
        )
        assert official.confidence_score > social.confidence_score

    def test_no_market_data_leaves_prices_unknown(self):
        opportunity = make_opportunity(
            product_name="No Data Item", brand="Brand X"
        )
        evaluation = evaluate_opportunity(opportunity)

        assert evaluation.target_buy_price is None
        assert evaluation.target_sell_price is None
        assert evaluation.estimated_profit is None
        assert "required spend / retail price" in evaluation.missing_information
        assert "resale price evidence" in evaluation.missing_information

    def test_falling_demand_penalizes_flip_and_demand_scores(self):
        base_fields = dict(
            product_name="Same Item",
            brand="Brand X",
            franchise="Brand X",
            required_spend=50.0,
            recent_sold_price=150.0,
        )
        falling = evaluate_opportunity(
            make_opportunity(**base_fields, demand_direction="FALLING")
        )
        rising = evaluate_opportunity(
            make_opportunity(**base_fields, demand_direction="RISING")
        )

        assert falling.flip_score < rising.flip_score
        assert falling.demand_score < rising.demand_score

    def test_a_product_that_has_peaked_should_be_avoided(self):
        # Only a peak_market_price is known - Module 3 must never use
        # it as the expected sell price, so this looks like a product
        # with no reliable resale evidence at all.
        opportunity = make_opportunity(
            product_name="Past Its Peak Item",
            brand="Brand X",
            required_spend=100.0,
            peak_market_price=1000.0,
            demand_direction="FALLING",
        )
        evaluation = evaluate_opportunity(opportunity)

        assert evaluation.target_sell_price is None
        assert evaluation.estimated_profit is None
        assert evaluation.recommendation in {"WATCH", "SKIP", "AVOID"}


# ---------------------------------------------------------------
# Demand direction
# ---------------------------------------------------------------

class TestDemandDirection:
    def test_surging_demand_boosts_flip_and_demand_scores(self):
        base_fields = dict(
            product_name="Same Item",
            brand="Brand X",
            franchise="Brand X",
            required_spend=50.0,
            recent_sold_price=150.0,
        )
        surging = evaluate_opportunity(
            make_opportunity(**base_fields, demand_direction="SURGING")
        )
        neutral = evaluate_opportunity(make_opportunity(**base_fields))

        assert surging.flip_score > neutral.flip_score
        assert surging.demand_score > neutral.demand_score


# ---------------------------------------------------------------
# Quantity recommendations
# ---------------------------------------------------------------

class TestRecommendedQuantity:
    def test_purchase_limit_of_one_caps_quantity(self):
        opportunity = round1_fixture_b()
        opportunity.purchase_limit = 1
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.recommended_quantity <= 1

    def test_never_exceeds_configured_maximum(self):
        opportunity = round1_fixture_b()
        opportunity.purchase_limit = None
        config = ScoringConfig()
        evaluation = evaluate_opportunity(opportunity, config=config)
        assert evaluation.recommended_quantity <= config.max_recommended_quantity

    def test_non_buy_tiers_recommend_zero_quantity(self):
        opportunity = make_opportunity(
            product_name="Weak Item", brand="Brand X"
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.recommendation not in {
            "CRITICAL_BUY", "STRONG_BUY", "BUY", "CONDITIONAL_BUY"
        }
        assert evaluation.recommended_quantity == 0


# ---------------------------------------------------------------
# Confidence caps and risk penalties
# ---------------------------------------------------------------

class TestConfidenceAndRisk:
    def test_low_confidence_caps_opportunity_score(self):
        opportunity = make_opportunity(
            product_name="Unclear Item",
            brand="Brand X",
            required_spend=10.0,
            recent_sold_price=1000.0,
            # No source_type, no franchise, no release info - thin
            # evidence despite a huge apparent spread.
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.opportunity_score <= (
            evaluation.confidence_score + 15.0 + 0.01
        )

    def test_confidence_below_minimum_blocks_buy_tier(self):
        config = ScoringConfig()
        config.recommendation_thresholds["CONDITIONAL_BUY"] = 1
        config.min_confidence_for_buy = 90.0

        opportunity = make_opportunity(
            product_name="Item",
            brand="Brand X",
            required_spend=10.0,
            recent_sold_price=100.0,
        )
        evaluation = evaluate_opportunity(opportunity, config=config)

        assert evaluation.recommendation not in {
            "CRITICAL_BUY", "STRONG_BUY", "BUY", "CONDITIONAL_BUY"
        }
        assert evaluation.blocking_reasons

    def test_extreme_risk_forces_avoid(self):
        config = ScoringConfig()
        # Every opportunity carries a baseline risk_score of 10 - set
        # the threshold below that so the forced-AVOID rule is
        # guaranteed to trigger regardless of other risk factors.
        config.max_risk_before_avoid = 5.0

        opportunity = make_opportunity(
            product_name="Moderate Item",
            brand="Brand X",
            franchise="Brand X",
            required_spend=50.0,
            recent_sold_price=150.0,
        )
        evaluation = evaluate_opportunity(opportunity, config=config)

        assert evaluation.recommendation == "AVOID"
        assert evaluation.blocking_reasons

    def test_risk_score_never_exceeds_100(self):
        opportunity = make_opportunity(
            product_name="Extreme Risk Item",
            brand="Brand X",
            status="rumored",
            demand_direction="FALLING",
            redeemable_reward=True,
            estimated_market_price=500.0,
            risks=["a", "b", "c", "d", "e", "f", "g"],
            required_spend=50.0,
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.risk_score <= 100


# ---------------------------------------------------------------
# Structural properties
# ---------------------------------------------------------------

class TestStructuralProperties:
    def test_recommendation_is_a_valid_enum_value(self):
        evaluation = evaluate_opportunity(round1_fixture_a())
        assert evaluation.recommendation in {r.value for r in Recommendation}

    def test_primary_strategy_is_a_valid_enum_value(self):
        evaluation = evaluate_opportunity(round1_fixture_b())
        assert evaluation.primary_strategy in {
            s.value for s in PrimaryStrategy
        }

    def test_all_component_scores_within_bounds(self):
        for opportunity in (
            round1_fixture_a(),
            round1_fixture_b(),
            make_opportunity(product_name="Bare", brand="Brand X"),
        ):
            evaluation = evaluate_opportunity(opportunity)

            for field_name in SCORE_FIELDS:
                value = getattr(evaluation, field_name)
                assert 0 <= value <= 100, f"{field_name}={value} out of bounds"

    def test_avoid_recommendation_implies_avoid_strategy(self):
        config = ScoringConfig()
        config.max_risk_before_avoid = 1.0

        opportunity = make_opportunity(
            product_name="Item", brand="Brand X", required_spend=10.0
        )
        evaluation = evaluate_opportunity(opportunity, config=config)

        assert evaluation.recommendation == "AVOID"
        assert evaluation.primary_strategy == "AVOID"

    def test_does_not_mutate_original_opportunity(self):
        opportunity = round1_fixture_a()
        before = opportunity.to_dict()

        evaluate_opportunity(opportunity)

        assert opportunity.to_dict() == before


# ---------------------------------------------------------------
# Price logic
# ---------------------------------------------------------------

class TestPriceLogic:
    def test_peak_market_price_alone_is_never_used_as_sell_price(self):
        opportunity = make_opportunity(
            product_name="Peaked Item",
            brand="Brand X",
            peak_market_price=999.0,
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.target_sell_price is None

    def test_recent_sold_price_takes_priority_over_current_and_estimated(self):
        opportunity = make_opportunity(
            product_name="Item",
            brand="Brand X",
            recent_sold_price=100.0,
            current_market_price=200.0,
            estimated_market_price=300.0,
            peak_market_price=400.0,
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.target_sell_price == 100.0

    def test_required_spend_takes_priority_over_retail_price(self):
        opportunity = make_opportunity(
            product_name="Item",
            brand="Brand X",
            required_spend=50.0,
            retail_price=80.0,
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.target_buy_price == 50.0

    def test_estimated_profit_and_roi_computed_when_both_prices_known(self):
        opportunity = make_opportunity(
            product_name="Item",
            brand="Brand X",
            required_spend=100.0,
            recent_sold_price=250.0,
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation.estimated_profit == 150.0
        assert evaluation.estimated_roi_percent == 150.0


# ---------------------------------------------------------------
# Configuration overrides
# ---------------------------------------------------------------

class TestConfigurationOverrides:
    def test_lowering_thresholds_upgrades_recommendation(self):
        opportunity = make_opportunity(
            product_name="Bare Item", brand="Brand X"
        )
        default_eval = evaluate_opportunity(opportunity)

        lenient_config = ScoringConfig()
        lenient_config.recommendation_thresholds["WATCH"] = 0
        lenient_eval = evaluate_opportunity(opportunity, config=lenient_config)

        assert RECOMMENDATION_ORDER.index(
            lenient_eval.recommendation
        ) <= RECOMMENDATION_ORDER.index(default_eval.recommendation)

    def test_context_overrides_win_over_computed_fields(self):
        opportunity = round1_fixture_a()
        context = ScoringContext(
            overrides={
                "collector_score": 99,
                "recommendation": "CRITICAL_BUY",
            }
        )
        evaluation = evaluate_opportunity(opportunity, context=context)

        assert evaluation.collector_score == 99
        assert evaluation.recommendation == "CRITICAL_BUY"

    def test_franchise_strength_context_boosts_collector_and_hold(self):
        opportunity = make_opportunity(
            product_name="Item",
            brand="Brand X",
            franchise="Brand X",
        )
        without_context = evaluate_opportunity(opportunity)
        with_context = evaluate_opportunity(
            opportunity,
            context=ScoringContext(franchise_strength=90),
        )

        assert with_context.collector_score > without_context.collector_score
        assert with_context.hold_score > without_context.hold_score

    def test_evaluate_opportunity_works_with_no_context_or_config(self):
        opportunity = make_opportunity(
            product_name="Item", brand="Brand X"
        )
        evaluation = evaluate_opportunity(opportunity)
        assert evaluation is not None


# ---------------------------------------------------------------
# Evidence-derived confidence
# ---------------------------------------------------------------

class TestEvidenceConfidence:
    def test_rumored_evidence_lowers_confidence(self):
        base_fields = dict(
            product_name="Item",
            brand="Brand X",
            required_spend=50.0,
            recent_sold_price=150.0,
        )
        confirmed = evaluate_opportunity(
            make_opportunity(
                **base_fields,
                evidence=[{"signal_type": "COLLABORATION", "confirmed": True}],
            )
        )
        rumored = evaluate_opportunity(
            make_opportunity(
                **base_fields,
                evidence=[{"signal_type": "RUMOR", "rumored": True}],
            )
        )
        assert rumored.confidence_score < confirmed.confidence_score
