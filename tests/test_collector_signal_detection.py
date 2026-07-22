"""
Atlas v21 - Module 2: Collector Signal Detection.

Tests the deterministic extraction primitives (extraction.py), the
detector orchestration (detector.py), and the opportunity builder
(opportunity_builder.py) - all without any network access.
"""

import pytest

from collector_intelligence import extraction
from collector_intelligence.detector import detect_signals
from collector_intelligence.opportunity_builder import (
    InsufficientIdentityError,
    build_partial_opportunity,
)
from collector_intelligence.signals import SignalType
from collector_intelligence.source_models import RawSourceInput


ROUND1_BODY = (
    "One Piece and Round1 launched a limited collaboration campaign. "
    "Customers who spent approximately $200 on eligible arcade play "
    "could receive four exclusive promotional card packs. The "
    "campaign was only available at participating Round1 locations "
    "for a limited time. Complete promo sets reportedly sold quickly "
    "for around $2,200 on the secondary market."
)


def make_source(**overrides):
    fields = {
        "title": "Test Source",
        "body": "",
        "source_type": "NEWS",
    }
    fields.update(overrides)
    return RawSourceInput(**fields)


# ---------------------------------------------------------------
# extraction.py: negation and unlimited override
# ---------------------------------------------------------------

class TestNegation:
    def test_negation_trigger_immediately_before_suppresses_match(self):
        text = "This is not a limited to 500 pieces release."
        assert extraction.is_locally_negated(
            text, text.index("limited")
        )

    def test_no_negation_trigger_nearby(self):
        text = "Limited to 500 pieces, available now."
        assert not extraction.is_locally_negated(
            text, text.index("500")
        )

    def test_unlimited_override_detected(self):
        assert extraction.has_unlimited_override(
            "Unlimited stock will be available."
        )

    def test_unlimited_override_absent(self):
        assert not extraction.has_unlimited_override(
            "Limited stock available now."
        )

    def test_limited_quantity_suppressed_by_negation(self):
        text = "This is not limited to 500 pieces."
        assert extraction.find_limited_quantity(text) is None

    def test_limited_quantity_suppressed_by_unlimited_override(self):
        text = "Limited to 500 pieces, but unlimited stock will follow."
        assert extraction.find_limited_quantity(text) is None


# ---------------------------------------------------------------
# extraction.py: certainty classification
# ---------------------------------------------------------------

class TestCertainty:
    def test_rumor_marker_wins_over_estimate_marker(self):
        text = "Allegedly, the set is approximately $200."
        position = text.index("$200")
        assert extraction.classify_certainty(text, position) == "rumored"

    def test_estimate_marker_detected(self):
        text = "The set reportedly costs $200."
        position = text.index("$200")
        assert extraction.classify_certainty(text, position) == "estimated"

    def test_confirmed_when_no_markers_present(self):
        text = "The set costs $200."
        position = text.index("$200")
        assert extraction.classify_certainty(text, position) == "confirmed"

    def test_certainty_flags_shape(self):
        assert extraction.certainty_flags("rumored") == {
            "confirmed": False,
            "estimated": False,
            "rumored": True,
        }
        assert extraction.certainty_flags("confirmed") == {
            "confirmed": True,
            "estimated": False,
            "rumored": False,
        }


# ---------------------------------------------------------------
# extraction.py: currency and price context
# ---------------------------------------------------------------

class TestCurrency:
    def test_dollar_amount_extracted(self):
        results = extraction.find_currency_amounts("Priced at $200.")
        assert len(results) == 1
        assert results[0]["amount"] == 200.0
        assert results[0]["currency"] == "USD"

    def test_dollar_amount_with_thousands_comma(self):
        results = extraction.find_currency_amounts(
            "Selling for $2,200 on the secondary market."
        )
        assert results[0]["amount"] == 2200.0

    def test_multiple_amounts_sorted_by_position(self):
        results = extraction.find_currency_amounts(
            "Spend $200 to get packs that resell for $2,200."
        )
        assert [r["amount"] for r in results] == [200.0, 2200.0]

    def test_spend_context_classified(self):
        text = "Customers who spent $200 on eligible purchases qualify."
        amount = extraction.find_currency_amounts(text)[0]
        context = extraction.classify_price_context(
            text, amount["start"], amount["end"]
        )
        assert context == "spend"

    def test_resale_context_classified(self):
        text = "Complete sets are selling for around $2,200."
        amount = extraction.find_currency_amounts(text)[0]
        context = extraction.classify_price_context(
            text, amount["start"], amount["end"]
        )
        assert context == "resale"

    def test_retail_context_classified(self):
        text = "The retail price is $60 at launch."
        amount = extraction.find_currency_amounts(text)[0]
        context = extraction.classify_price_context(
            text, amount["start"], amount["end"]
        )
        assert context == "retail"

    def test_unclassified_context_returns_none(self):
        text = "A random number $60 appears here."
        amount = extraction.find_currency_amounts(text)[0]
        context = extraction.classify_price_context(
            text, amount["start"], amount["end"]
        )
        assert context is None

    def test_mentions_complete_set(self):
        text = "Complete sets are selling for around $2,200."
        amount = extraction.find_currency_amounts(text)[0]
        assert extraction.mentions_complete_set(
            text, amount["start"], amount["end"]
        )

    def test_does_not_mention_complete_set(self):
        text = "A single card is selling for around $2,200."
        amount = extraction.find_currency_amounts(text)[0]
        assert not extraction.mentions_complete_set(
            text, amount["start"], amount["end"]
        )


# ---------------------------------------------------------------
# extraction.py: quantities
# ---------------------------------------------------------------

class TestQuantities:
    def test_limited_quantity_numeric(self):
        result = extraction.find_limited_quantity(
            "Limited to 500 pieces."
        )
        assert result["value"] == 500

    def test_purchase_limit(self):
        result = extraction.find_purchase_limit(
            "Limit 1 per customer."
        )
        assert result["value"] == 1

    def test_purchase_limit_negated(self):
        assert extraction.find_purchase_limit(
            "There is no limit 1 per customer restriction."
        ) is None

    def test_pack_quantity_word_number(self):
        result = extraction.find_pack_quantity(
            "Customers receive four exclusive promotional card packs."
        )
        assert result["value"] == 4

    def test_pack_quantity_digit(self):
        result = extraction.find_pack_quantity(
            "Customers receive 4 promotional packs."
        )
        assert result["value"] == 4

    def test_numbered_release_detected(self):
        result = extraction.find_numbered_release(
            "Each piece is individually numbered."
        )
        assert result is not None

    def test_numbered_release_absent(self):
        assert extraction.find_numbered_release(
            "A standard mass-produced item."
        ) is None

    def test_word_to_number(self):
        assert extraction.word_to_number("four") == 4
        assert extraction.word_to_number("12") == 12
        assert extraction.word_to_number("unknown") is None


# ---------------------------------------------------------------
# extraction.py: dates, windows, durations
# ---------------------------------------------------------------

class TestDatesAndWindows:
    def test_find_dates(self):
        results = extraction.find_dates("Releasing on July 20, 2026.")
        assert results[0]["month"] == "July"
        assert results[0]["day"] == "20"
        assert results[0]["year"] == "2026"

    def test_purchase_window_two_months(self):
        result = extraction.find_purchase_window(
            "Available July 20 through August 4."
        )
        assert result["window_start"] == "July 20"
        assert result["window_end"] == "August 4"

    def test_purchase_window_single_month(self):
        result = extraction.find_purchase_window(
            "Available July 20 through July 30."
        )
        assert result["window_start"] == "July 20"
        assert result["window_end"] == "July 30"

    def test_sellout_duration(self):
        result = extraction.find_sellout_duration(
            "Sold out within 30 minutes."
        )
        assert result["value"] == 30
        assert result["unit"] == "minute"

    def test_release_time(self):
        result = extraction.find_release_time(
            "Doors open at 9:00 AM sharp."
        )
        assert result is not None
        assert "9:00 AM" in result["matched_text"]


# ---------------------------------------------------------------
# extraction.py: collaboration detection
# ---------------------------------------------------------------

class TestCollaborationExtraction:
    def test_and_launched_pattern(self):
        result = extraction.find_collaboration(
            "One Piece and Round1 launched a limited collaboration."
        )
        assert result["left"] == "One Piece"
        assert result["right"] == "Round1"

    def test_separator_pattern(self):
        result = extraction.find_collaboration(
            "The Sanrio x Starbucks collection sold out fast."
        )
        assert result["left"] == "Sanrio"
        assert result["right"] == "Starbucks"

    def test_single_sided_collaboration_with(self):
        result = extraction.find_collaboration(
            "Pokemon revealed a collaboration with Van Gogh Museum."
        )
        assert result["left"] is None
        assert result["right"] == "Van Gogh Museum"

    def test_single_sided_partnered_with(self):
        result = extraction.find_collaboration(
            "The brand partnered with Round1 for a summer campaign."
        )
        assert result["right"] == "Round1"

    def test_no_collaboration_found(self):
        assert extraction.find_collaboration(
            "This is a plain restock announcement."
        ) is None

    def test_negated_collaboration_suppressed(self):
        assert extraction.find_collaboration(
            "This is not a collaboration with Round1."
        ) is None

    def test_has_collaboration_keyword(self):
        assert extraction.has_collaboration_keyword(
            "A new crossover event begins today."
        )
        assert not extraction.has_collaboration_keyword(
            "A new item is now in stock."
        )

    def test_name_part_does_not_cross_newline(self):
        # Regression: title/body are joined with "\n" in
        # RawSourceInput.full_text. A name span must never splice
        # words from one line into another.
        text = "Round1 Collaboration\nOne Piece and Round1 launched a limited collaboration."
        result = extraction.find_collaboration(text)
        assert result["left"] == "One Piece"
        assert "\n" not in result["left"]

    def test_separator_match_retries_after_leading_filler_words(self):
        # Regression: finditer only yields non-overlapping matches. A
        # greedy match starting at a lowercase filler word ("from the
        # One Piece x Round1...") fails the proper-noun check, but a
        # plain finditer loop had already consumed that span and never
        # retried starting exactly at "One Piece" - silently missing a
        # real collaboration mention buried mid-sentence.
        text = (
            "Complete promo sets from the One Piece x Round1 collaboration "
            "reportedly sold for approximately $2,200 on the secondary market."
        )
        result = extraction.find_collaboration(text)
        assert result["left"] == "One Piece"
        assert result["right"] == "Round1"

    def test_separator_requires_word_boundary_around_x(self):
        # Regression: an unbounded "x" separator matched inside plain
        # words (e.g. "appro-x-imately"), producing garbage matches.
        text = "The price is approximately $200 for the item."
        result = extraction.find_collaboration(text)
        assert result is None

    def test_campaign_title_style_name_trims_promotional_filler(self):
        # Regression: a campaign-title-style mention ("BRAND x PARTNER
        # PROMOTIONAL PACK CAMPAIGN") captured "PARTNER PROMOTIONAL
        # PACK" as the partner name, since neither word was recognized
        # as trailing filler.
        text = "ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN"
        result = extraction.find_collaboration(text)
        assert result["right"] == "ROUND1"

    def test_listing_title_style_name_trims_complete_set_filler(self):
        # Regression: a listing-title-style mention ("One Piece x
        # Round1 Complete Promo Set") captured "Round1 Complete" as
        # the partner name, since "complete"/"set" weren't recognized
        # as trailing filler.
        text = "One Piece x Round1 Complete Promo Set"
        result = extraction.find_collaboration(text)
        assert result["right"] == "Round1"


# ---------------------------------------------------------------
# detector.py: keyword and structured signal detection
# ---------------------------------------------------------------

class TestDetectorSignals:
    def test_anniversary_signal(self):
        source = make_source(
            body="Celebrating the 25th anniversary of the franchise."
        )
        result = detect_signals(source)
        assert result.has_signal(SignalType.ANNIVERSARY)

    def test_membership_exclusive_signal(self):
        source = make_source(
            body="This product is members only at launch."
        )
        result = detect_signals(source)
        assert result.has_signal(SignalType.MEMBERSHIP_EXCLUSIVE)

    def test_lottery_signal(self):
        source = make_source(
            body="Entry is via a lottery for a chance to purchase."
        )
        result = detect_signals(source)
        assert result.has_signal(SignalType.LOTTERY_REQUIRED)

    def test_rapid_sellout_keyword_signal(self):
        source = make_source(body="The drop sold out immediately.")
        result = detect_signals(source)
        assert result.has_signal(SignalType.RAPID_SELLOUT)

    def test_rapid_sellout_duration_signal_has_value(self):
        source = make_source(body="Sold out within 30 minutes.")
        result = detect_signals(source)
        durations = result.signals_of_type(SignalType.RAPID_SELLOUT)
        assert any(s.extracted_value == 30 for s in durations)

    def test_status_sold_out_signal(self):
        source = make_source(body="The item is sold out everywhere.")
        result = detect_signals(source)
        assert result.has_signal(SignalType.STATUS_SOLD_OUT)

    def test_status_restocked_signal(self):
        source = make_source(body="The item was restocked overnight.")
        result = detect_signals(source)
        assert result.has_signal(SignalType.STATUS_RESTOCKED)

    def test_sealed_product_signal(self):
        source = make_source(body="Still factory sealed in the box.")
        result = detect_signals(source)
        assert result.has_signal(SignalType.SEALED_PRODUCT)

    def test_rumor_signal_marks_detection_rumored(self):
        source = make_source(
            body="Allegedly, a new Pokemon collaboration is coming."
        )
        result = detect_signals(source)
        rumor_signals = result.signals_of_type(SignalType.RUMOR)
        assert rumor_signals
        assert rumor_signals[0].rumored is True

    def test_price_signal_confidence_lowered_for_estimate(self):
        confirmed_source = make_source(
            body="One Piece and Round1 launched a collaboration. The "
            "spend requirement is $200 on eligible purchases."
        )
        estimated_source = make_source(
            body="One Piece and Round1 launched a collaboration. "
            "Customers reportedly spent approximately $200 on "
            "eligible purchases."
        )
        confirmed_result = detect_signals(confirmed_source)
        estimated_result = detect_signals(estimated_source)

        confirmed_spend = confirmed_result.signals_of_type(
            SignalType.SPEND_REQUIREMENT
        )[0]
        estimated_spend = estimated_result.signals_of_type(
            SignalType.SPEND_REQUIREMENT
        )[0]

        assert estimated_spend.confidence < confirmed_spend.confidence

    def test_high_acquisition_difficulty_requires_two_barriers(self):
        single_barrier_source = make_source(
            body="One Piece and Round1 launched a collaboration "
            "requiring a $200 spend to participate."
        )
        result = detect_signals(single_barrier_source)
        # Only SPEND_REQUIREMENT present as a barrier type - not
        # enough on its own to derive HIGH_ACQUISITION_DIFFICULTY.
        assert not result.has_signal(
            SignalType.HIGH_ACQUISITION_DIFFICULTY
        )

    def test_high_acquisition_difficulty_derived_from_two_barriers(self):
        result = detect_signals(make_source(body=ROUND1_BODY))
        assert result.has_signal(
            SignalType.HIGH_ACQUISITION_DIFFICULTY
        )

    def test_risk_warning_for_complete_set_resale_price(self):
        source = make_source(
            body="Complete sets are selling for around $2,200 on the "
            "secondary market."
        )
        result = detect_signals(source)
        assert result.has_signal(SignalType.RISK_WARNING)


# ---------------------------------------------------------------
# detector.py: entity extraction
# ---------------------------------------------------------------

class TestEntityExtraction:
    def test_collaboration_populates_entities(self):
        result = detect_signals(make_source(body=ROUND1_BODY))
        entities = result.extracted_entities
        assert entities.franchise == "One Piece"
        assert entities.brand == "One Piece"
        assert entities.collaboration_partner == "Round1"

    def test_hints_populate_entities_when_no_collaboration(self):
        source = make_source(
            body="A new restock was announced today.",
            brand_hint="Pokemon",
            franchise_hint="Pokemon TCG",
            retailer="Target",
        )
        result = detect_signals(source)
        entities = result.extracted_entities
        assert entities.brand == "Pokemon"
        assert entities.franchise == "Pokemon TCG"
        assert entities.retailer == "Target"

    def test_no_identity_when_nothing_present(self):
        source = make_source(body="A generic announcement with no names.")
        result = detect_signals(source)
        assert not result.extracted_entities.has_any_identity()


# ---------------------------------------------------------------
# detector.py: relevance scoring and should_create_opportunity
# ---------------------------------------------------------------

class TestShouldCreateOpportunity:
    def test_strong_collaboration_fixture_creates_opportunity(self):
        result = detect_signals(make_source(body=ROUND1_BODY))
        assert result.should_create_opportunity is True
        assert result.rejection_reason is None

    def test_ordinary_restock_is_rejected(self):
        source = make_source(
            body="The item is back in stock at the usual retail price "
            "of $20.",
            brand_hint="Generic Brand",
        )
        result = detect_signals(source)
        assert result.should_create_opportunity is False
        assert result.rejection_reason is not None

    def test_no_identity_is_rejected_with_reason(self):
        source = make_source(
            body="Allegedly something is happening soon."
        )
        result = detect_signals(source)
        assert result.should_create_opportunity is False
        assert result.rejection_reason == "missing_product_identity"

    def test_missing_product_identity_flagged(self):
        source = make_source(body="Prices went up this week.")
        result = detect_signals(source)
        assert "product_identity" in result.missing_critical_fields

    def test_insufficient_identity_warning_for_rumor(self):
        source = make_source(
            body="Rumor has it something big is coming soon."
        )
        result = detect_signals(source)
        assert any(
            "deduplication key" in warning
            for warning in result.warnings
        )


# ---------------------------------------------------------------
# detector.py: source-type confidence adjustment
# ---------------------------------------------------------------

class TestSourceTypeConfidenceAdjustment:
    def test_official_source_boosts_confidence(self):
        official = make_source(
            body=ROUND1_BODY, source_type="OFFICIAL"
        )
        social = make_source(
            body=ROUND1_BODY, source_type="SOCIAL"
        )

        official_result = detect_signals(official)
        social_result = detect_signals(social)

        official_collab = official_result.signals_of_type(
            SignalType.COLLABORATION
        )[0]
        social_collab = social_result.signals_of_type(
            SignalType.COLLABORATION
        )[0]

        assert official_collab.confidence > social_collab.confidence


# ---------------------------------------------------------------
# opportunity_builder.py
# ---------------------------------------------------------------

class TestOpportunityBuilder:
    def test_builds_opportunity_from_round1_fixture(self):
        source = make_source(
            title="One Piece x Round1 Collaboration",
            body=ROUND1_BODY,
            source_type="NEWS",
        )
        result = detect_signals(source)
        opportunity = build_partial_opportunity(result)

        assert opportunity.brand == "One Piece"
        assert opportunity.franchise == "One Piece"
        assert opportunity.collaboration_partner == "Round1"
        assert opportunity.required_spend == 200.0
        assert opportunity.recent_sold_price == 2200.0
        assert opportunity.currency == "USD"
        assert opportunity.exclusive_promo is True
        assert opportunity.retailer_exclusive is True
        assert opportunity.estimated_profit == 2000.0

    def test_never_sets_scores_or_recommendation_by_default(self):
        source = make_source(title="Fixture", body=ROUND1_BODY)
        result = detect_signals(source)
        opportunity = build_partial_opportunity(result)

        assert opportunity.collector_score is None
        assert opportunity.flip_score is None
        assert opportunity.hold_score is None
        assert opportunity.recommendation is None
        assert opportunity.primary_strategy is None
        assert opportunity.acquisition_difficulty is None

    def test_overrides_win_over_signal_derived_fields(self):
        source = make_source(title="Fixture", body=ROUND1_BODY)
        result = detect_signals(source)
        opportunity = build_partial_opportunity(
            result,
            overrides={
                "collector_score": 90,
                "recommendation": "STRONG_BUY",
                "brand": "Custom Brand",
            },
        )

        assert opportunity.collector_score == 90
        assert opportunity.recommendation == "STRONG_BUY"
        assert opportunity.brand == "Custom Brand"

    def test_product_name_falls_back_to_source_title(self):
        source = make_source(
            title="One Piece x Round1 Collaboration",
            body=ROUND1_BODY,
        )
        result = detect_signals(source)
        opportunity = build_partial_opportunity(result)
        assert (
            opportunity.product_name
            == "One Piece x Round1 Collaboration"
        )

    def test_raises_when_identity_cannot_be_resolved(self):
        source = RawSourceInput(
            title="",
            body="A generic announcement with no identifiable names.",
        )
        result = detect_signals(source)

        with pytest.raises(InsufficientIdentityError):
            build_partial_opportunity(result)

    def test_dedup_key_reflects_retailer(self):
        source_a = make_source(
            title="One Piece x Round1 Collaboration",
            body=ROUND1_BODY,
            retailer="Round1",
        )
        source_b = make_source(
            title="One Piece x Round1 Collaboration",
            body=ROUND1_BODY,
            retailer="Different Retailer",
        )

        opportunity_a = build_partial_opportunity(
            detect_signals(source_a)
        )
        opportunity_b = build_partial_opportunity(
            detect_signals(source_b)
        )

        assert opportunity_a.dedup_key != opportunity_b.dedup_key

    def test_risks_include_complete_set_and_acquisition_difficulty(self):
        source = make_source(title="Fixture", body=ROUND1_BODY)
        opportunity = build_partial_opportunity(
            detect_signals(source)
        )
        assert any(
            "complete set" in risk for risk in opportunity.risks
        )
        assert any(
            "acquisition barriers" in risk
            for risk in opportunity.risks
        )

    def test_catalyst_signals_populated(self):
        source = make_source(title="Fixture", body=ROUND1_BODY)
        opportunity = build_partial_opportunity(
            detect_signals(source)
        )
        assert opportunity.catalyst_signals
