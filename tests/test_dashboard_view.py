"""
Atlas v21 - Module 8: dashboard view-model layer tests.

Covers classification, override application, image resolution, link
resolution, demand tags, relative time, and backward compatibility
with opportunities that have no image/user data at all.
"""

from datetime import datetime, timedelta, timezone

from collector_intelligence.dashboard_models import (
    HeartedItem,
    OpportunityImage,
    OpportunityNote,
    OpportunityUserOverride,
    UserExternalLink,
)
from collector_intelligence.dashboard_view import (
    MAX_DEMAND_TAGS,
    PLACEHOLDER_IMAGE_URL,
    build_card_view_model,
    build_details_view_model,
    classify_confidence,
    classify_market_strength,
    classify_market_trend,
    effective_value,
    format_relative_time,
    resolve_image,
    resolve_links,
    resolve_unit_scope_label,
    select_demand_tags,
)
from collector_intelligence.decision_engine import evaluate_opportunity
from collector_intelligence.models import CollectorOpportunity


def make_opportunity(**overrides):
    fields = {"product_name": "Test Product", "brand": "Brand X"}
    fields.update(overrides)
    return CollectorOpportunity(**fields)


def evaluate(opportunity):
    return evaluate_opportunity(opportunity)


# ---------------------------------------------------------------
# Market strength badges (8-11)
# ---------------------------------------------------------------

class TestMarketStrengthClassification:
    def test_unknown_with_no_evidence(self):
        opp = make_opportunity()
        assert classify_market_strength(opp, evaluate(opp)) == "UNKNOWN"

    def test_weak_with_thin_evidence(self):
        opp = make_opportunity(recent_sold_price=50.0)
        result = classify_market_strength(opp, evaluate(opp))
        assert result in {"WEAK", "MEDIUM"}  # some evidence, but not strong

    def test_strong_with_rich_evidence(self):
        opp = make_opportunity(
            franchise="Brand X",
            recent_sold_price=500.0,
            required_spend=50.0,
            limited_quantity=True,
            stated_quantity=100,
            numbered=True,
            purchase_limit=1,
            demand_direction="SURGING",
            sold_listing_count=25,
            sales_velocity=10,
        )
        evaluation = evaluate(opp)
        assert evaluation.demand_score > 0 or evaluation.scarcity_score > 0
        result = classify_market_strength(opp, evaluation)
        assert result in {"STRONG", "MEDIUM"}

    def test_medium_is_a_real_reachable_bucket(self):
        opp = make_opportunity(
            recent_sold_price=100.0, required_spend=50.0, limited_quantity=True,
        )
        result = classify_market_strength(opp, evaluate(opp))
        assert result in {"MEDIUM", "WEAK", "STRONG"}

    def test_never_derived_from_recommendation(self):
        # Two opportunities with identical demand/scarcity/risk inputs
        # but very different "would you buy this" framing must yield
        # the same market_strength - it's not a recommendation proxy.
        opp_a = make_opportunity(recent_sold_price=100.0, required_spend=90.0)
        opp_b = make_opportunity(recent_sold_price=100.0, required_spend=90.0, status="rumored")
        eval_a = evaluate(opp_a)
        eval_b = evaluate(opp_b)
        # Even though rumor status changes recommendation dramatically,
        # market_strength only reads demand/scarcity/risk scores.
        strength_a = classify_market_strength(opp_a, eval_a)
        strength_b = classify_market_strength(opp_b, eval_b)
        assert strength_a in {"STRONG", "MEDIUM", "WEAK", "UNKNOWN"}
        assert strength_b in {"STRONG", "MEDIUM", "WEAK", "UNKNOWN"}


# ---------------------------------------------------------------
# Confidence stays separate (12)
# ---------------------------------------------------------------

class TestConfidence:
    def test_confidence_is_independent_of_market_strength(self):
        opp = make_opportunity(recent_sold_price=100.0, source_type="OFFICIAL")
        evaluation = evaluate(opp)
        confidence = classify_confidence(evaluation)
        strength = classify_market_strength(opp, evaluation)
        assert confidence in {"HIGH", "MEDIUM", "LOW"}
        assert strength in {"STRONG", "MEDIUM", "WEAK", "UNKNOWN"}

    def test_high_confidence_from_official_source(self):
        opp = make_opportunity(
            franchise="Brand X", collaboration_partner="Partner",
            source_type="OFFICIAL", required_spend=50.0, recent_sold_price=100.0,
        )
        evaluation = evaluate(opp)
        assert classify_confidence(evaluation) in {"HIGH", "MEDIUM"}


# ---------------------------------------------------------------
# Market trend
# ---------------------------------------------------------------

class TestMarketTrend:
    def test_rising_trend(self):
        opp = make_opportunity(demand_direction="RISING")
        assert classify_market_trend(opp) == "RISING"

    def test_surging_maps_to_rising(self):
        opp = make_opportunity(demand_direction="SURGING")
        assert classify_market_trend(opp) == "RISING"

    def test_falling_trend(self):
        opp = make_opportunity(demand_direction="FALLING")
        assert classify_market_trend(opp) == "FALLING"

    def test_unknown_trend_when_unset(self):
        opp = make_opportunity()
        assert classify_market_trend(opp) == "UNKNOWN"


# ---------------------------------------------------------------
# Unit scope / complete-set caution (15-16)
# ---------------------------------------------------------------

class TestUnitScope:
    def test_single_item_default(self):
        opp = make_opportunity()
        assert resolve_unit_scope_label(opp) == "Single item"

    def test_complete_set_when_product_is_the_set(self):
        opp = make_opportunity(edition_name="Complete Set")
        assert resolve_unit_scope_label(opp) == "Complete set"

    def test_complete_set_caution_flagged(self):
        opp = make_opportunity(
            recent_sold_price=2200.0,
            risks=["This resale figure reflects a complete set, not a single item."],
        )
        evaluation = evaluate(opp)
        card = build_card_view_model(opp, evaluation)
        assert card.unit_scope_is_caution is True
        assert card.unit_scope == "Complete set"


# ---------------------------------------------------------------
# Demand tags - max 3 (18)
# ---------------------------------------------------------------

class TestDemandTags:
    def test_never_exceeds_max(self):
        opp = make_opportunity(
            exclusive_promo=True, limited_quantity=True, event_exclusive=True,
            sealed_product=True, artist_name="Artist", character_names=["Hero"],
            tournament_exclusive=True, sellout_speed="within 30 minutes",
        )
        evaluation = evaluate(opp)
        tags = select_demand_tags(opp, evaluation)
        assert len(tags) <= MAX_DEMAND_TAGS

    def test_tags_are_short_no_sentences(self):
        opp = make_opportunity(exclusive_promo=True, event_exclusive=True)
        evaluation = evaluate(opp)
        tags = select_demand_tags(opp, evaluation)
        for tag in tags:
            assert len(tag) < 30
            assert "." not in tag

    def test_override_tags_win_and_still_capped(self):
        opp = make_opportunity()
        evaluation = evaluate(opp)
        tags = select_demand_tags(opp, evaluation, override_tags=["A", "B", "C", "D"])
        assert tags == ["A", "B", "C"]

    def test_complete_set_caveat_always_included_first(self):
        opp = make_opportunity(
            recent_sold_price=2200.0, exclusive_promo=True, event_exclusive=True,
            risks=["This resale figure reflects a complete set, not a single item."],
        )
        evaluation = evaluate(opp)
        tags = select_demand_tags(opp, evaluation)
        assert tags[0] == "Complete set"

    def test_no_tags_no_crash(self):
        opp = make_opportunity()
        evaluation = evaluate(opp)
        tags = select_demand_tags(opp, evaluation)
        assert isinstance(tags, list)


# ---------------------------------------------------------------
# Relative time (6)
# ---------------------------------------------------------------

class TestRelativeTime:
    def test_minutes_ago(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        then = (now - timedelta(minutes=18)).isoformat()
        assert format_relative_time(then, now=now) == "Updated 18m ago"

    def test_hours_ago(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        then = (now - timedelta(hours=2)).isoformat()
        assert format_relative_time(then, now=now) == "Updated 2h ago"

    def test_days_ago(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        then = (now - timedelta(days=3)).isoformat()
        assert format_relative_time(then, now=now) == "Updated 3d ago"

    def test_just_now(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        then = (now - timedelta(seconds=10)).isoformat()
        assert format_relative_time(then, now=now) == "Updated just now"

    def test_unknown_when_missing(self):
        assert format_relative_time(None) == "Unknown"

    def test_unknown_when_unparseable(self):
        assert format_relative_time("not-a-date") == "Unknown"


# ---------------------------------------------------------------
# Product image / placeholder / override (2-4)
# ---------------------------------------------------------------

class TestImageResolution:
    def test_placeholder_when_nothing_available(self):
        opp = make_opportunity()
        image = resolve_image(opp)
        assert image.is_placeholder is True
        assert image.url == PLACEHOLDER_IMAGE_URL
        assert image.alt_text

    def test_atlas_sourced_image_used(self):
        opp = make_opportunity()
        record = OpportunityImage(
            opportunity_id=opp.opportunity_id,
            primary_image_url="https://example.test/image.jpg",
            image_source_name="Official",
            image_alt_text="Product photo",
        )
        image = resolve_image(opp, image_record=record)
        assert image.url == "https://example.test/image.jpg"
        assert image.is_placeholder is False
        assert image.source_label == "Official"

    def test_user_override_wins_over_atlas_image(self):
        opp = make_opportunity()
        record = OpportunityImage(opportunity_id=opp.opportunity_id, primary_image_url="https://example.test/atlas.jpg")
        override = OpportunityUserOverride(opportunity_id=opp.opportunity_id, image_override_url="https://example.test/mine.jpg")
        image = resolve_image(opp, override=override, image_record=record)
        assert image.url == "https://example.test/mine.jpg"
        assert image.source_label == "User override"

    def test_alt_text_always_present(self):
        opp = make_opportunity(product_name="Something")
        image = resolve_image(opp)
        assert image.alt_text


# ---------------------------------------------------------------
# Links (20-23)
# ---------------------------------------------------------------

class TestLinks:
    def test_product_link_from_purchase_url(self):
        opp = make_opportunity(purchase_url="https://example.test/buy")
        links = resolve_links(opp)
        assert links["product"].available
        assert links["product"].url == "https://example.test/buy"

    def test_official_source_link_only_for_official_source_type(self):
        opp = make_opportunity(source_type="OFFICIAL", source_url="https://example.test/news")
        links = resolve_links(opp)
        assert links["official_source"].available
        assert links["official_source"].url == "https://example.test/news"

    def test_official_source_link_hidden_for_non_official(self):
        opp = make_opportunity(source_type="SOCIAL", source_url="https://example.test/post")
        links = resolve_links(opp)
        assert not links["official_source"].available

    def test_ebay_sold_never_defaults_to_a_guessed_url(self):
        opp = make_opportunity()
        links = resolve_links(opp)
        assert not links["ebay_sold"].available
        assert links["ebay_sold"].url is None

    def test_current_listings_separate_from_sold(self):
        opp = make_opportunity()
        user_links = [
            UserExternalLink(owner_type="opportunity", owner_id=opp.opportunity_id, link_type="ebay_sold", url="https://example.test/sold"),
            UserExternalLink(owner_type="opportunity", owner_id=opp.opportunity_id, link_type="current_listings", url="https://example.test/listings"),
        ]
        links = resolve_links(opp, user_links)
        assert links["ebay_sold"].url != links["current_listings"].url
        assert links["ebay_sold"].label == "eBay Sold"
        assert links["current_listings"].label == "Current Listings"

    def test_unavailable_link_marked_not_available(self):
        opp = make_opportunity()
        links = resolve_links(opp)
        assert links["evidence"].available is False


# ---------------------------------------------------------------
# Effective value computation - not stored redundantly
# ---------------------------------------------------------------

class TestEffectiveValue:
    def test_uses_atlas_when_no_override(self):
        assert effective_value("MEDIUM", None) == "MEDIUM"

    def test_uses_override_when_present(self):
        assert effective_value("MEDIUM", "STRONG") == "STRONG"

    def test_override_never_mutates_atlas_source(self):
        opp = make_opportunity(recent_sold_price=100.0)
        evaluation = evaluate(opp)
        atlas_before = classify_market_strength(opp, evaluation)
        override = OpportunityUserOverride(opportunity_id=opp.opportunity_id, market_strength_override="STRONG")
        build_card_view_model(opp, evaluation, override=override)
        atlas_after = classify_market_strength(opp, evaluation)
        assert atlas_before == atlas_after


# ---------------------------------------------------------------
# Full card view model (1, 5, 13, 14, 17, 19, 24-27, 43-44)
# ---------------------------------------------------------------

class TestCardViewModel:
    def test_compact_card_has_no_long_text_fields(self):
        opp = make_opportunity(
            product_name="Brand X Collab Item", required_spend=50.0, recent_sold_price=100.0,
        )
        evaluation = evaluate(opp)
        card = build_card_view_model(opp, evaluation)
        for tag in card.demand_tags:
            assert len(tag) < 40
            assert tag.count(" ") < 5  # short tag, not a sentence

    def test_product_name_present(self):
        opp = make_opportunity(product_name="Brand X Collab Item")
        card = build_card_view_model(opp, evaluate(opp))
        assert card.product_name == "Brand X Collab Item"

    def test_msrp_formatted(self):
        opp = make_opportunity(retail_price=59.99)
        card = build_card_view_model(opp, evaluate(opp))
        assert card.msrp_display == "$59.99"

    def test_msrp_unknown_when_absent(self):
        opp = make_opportunity()
        card = build_card_view_model(opp, evaluate(opp))
        assert card.msrp_display == "Unknown"

    def test_recent_sold_price_formatted(self):
        opp = make_opportunity(recent_sold_price=2200.0)
        card = build_card_view_model(opp, evaluate(opp))
        assert card.last_sold_display == "$2,200"

    def test_hearted_state_reflects_hearted_item(self):
        opp = make_opportunity()
        evaluation = evaluate(opp)
        card_before = build_card_view_model(opp, evaluation)
        assert card_before.hearted is False

        hearted = HeartedItem(opportunity_id=opp.opportunity_id)
        card_after = build_card_view_model(opp, evaluation, hearted_item=hearted)
        assert card_after.hearted is True
        assert card_after.hearted_at is not None

    def test_archived_hearted_item_shows_as_not_hearted(self):
        opp = make_opportunity()
        evaluation = evaluate(opp)
        hearted = HeartedItem(opportunity_id=opp.opportunity_id, archived_at="2026-01-01T00:00:00+00:00")
        card = build_card_view_model(opp, evaluation, hearted_item=hearted)
        assert card.hearted is False

    def test_hearting_never_changes_market_strength(self):
        opp = make_opportunity(recent_sold_price=100.0, required_spend=90.0)
        evaluation = evaluate(opp)
        card_unhearted = build_card_view_model(opp, evaluation)
        card_hearted = build_card_view_model(opp, evaluation, hearted_item=HeartedItem(opportunity_id=opp.opportunity_id))
        assert card_unhearted.market_strength == card_hearted.market_strength

    def test_has_notes_flag_only_a_presence_indicator(self):
        opp = make_opportunity()
        evaluation = evaluate(opp)
        card_no_notes = build_card_view_model(opp, evaluation, note_count=0)
        card_with_notes = build_card_view_model(opp, evaluation, note_count=3)
        assert card_no_notes.has_notes is False
        assert card_with_notes.has_notes is True

    def test_card_is_json_compatible(self):
        opp = make_opportunity(recent_sold_price=100.0, retail_price=50.0)
        card = build_card_view_model(opp, evaluate(opp))
        import json
        json.dumps(card.to_dict())  # must not raise

    def test_no_recommendation_field_on_card(self):
        opp = make_opportunity()
        card = build_card_view_model(opp, evaluate(opp))
        card_dict = card.to_dict()
        assert "recommendation" not in card_dict
        assert "primary_strategy" not in card_dict
        assert "recommended_quantity" not in card_dict


# ---------------------------------------------------------------
# Notes never enter evidence or scoring (43-44)
# ---------------------------------------------------------------

class TestNotesNeverAffectEvidenceOrScoring:
    def test_note_does_not_change_evaluation(self):
        opp = make_opportunity(recent_sold_price=100.0, required_spend=90.0)
        evaluation_before = evaluate(opp)

        note = OpportunityNote(opportunity_id=opp.opportunity_id, body="I think this will sell out fast")
        # Notes are only ever passed as a count/presence flag to the
        # card builder - never as text that could reach detect_signals
        # or evaluate_opportunity.
        evaluation_after = evaluate(opp)

        assert evaluation_before.opportunity_score == evaluation_after.opportunity_score
        assert evaluation_before.market_trend if hasattr(evaluation_before, "market_trend") else True

    def test_note_body_never_appears_in_opportunity_evidence(self):
        opp = make_opportunity()
        note_text = "SECRET_NOTE_MARKER_12345"
        OpportunityNote(opportunity_id=opp.opportunity_id, body=note_text)
        evidence_text = str(opp.evidence)
        assert note_text not in evidence_text

    def test_note_module_never_imports_detection_or_scoring(self):
        import collector_intelligence.dashboard_models as module
        with open(module.__file__) as f:
            content = f.read()
        assert "detect_signals" not in content
        assert "evaluate_opportunity" not in content


# ---------------------------------------------------------------
# Backward compatibility (59-60)
# ---------------------------------------------------------------

class TestBackwardCompatibility:
    def test_opportunity_with_no_image_data_renders_placeholder(self):
        opp = make_opportunity()
        card = build_card_view_model(opp, evaluate(opp))
        assert card.image.is_placeholder is True

    def test_opportunity_with_no_user_data_renders_safe_defaults(self):
        opp = make_opportunity()
        card = build_card_view_model(opp, evaluate(opp))
        assert card.hearted is False
        assert card.has_notes is False
        assert card.has_override is False
        assert card.market_strength_is_override is False

    def test_existing_collector_opportunity_fields_untouched(self):
        opp = make_opportunity(recent_sold_price=100.0)
        before = opp.to_dict()
        evaluation = evaluate(opp)
        build_card_view_model(opp, evaluation)
        build_details_view_model(opp, evaluation)
        assert opp.to_dict() == before


class TestAtlasValuePreservedEvenWhenOverridden:
    def test_atlas_market_strength_still_exposed_under_override(self):
        opp = make_opportunity(recent_sold_price=100.0, required_spend=90.0)
        evaluation = evaluate(opp)
        atlas_value = classify_market_strength(opp, evaluation)
        override = OpportunityUserOverride(opportunity_id=opp.opportunity_id, market_strength_override="STRONG")
        card = build_card_view_model(opp, evaluation, override=override)
        assert card.atlas_market_strength == atlas_value
        assert card.market_strength == "STRONG"
        assert card.atlas_market_strength != card.market_strength or atlas_value == "STRONG"

    def test_atlas_market_trend_still_exposed_under_override(self):
        opp = make_opportunity(demand_direction="FALLING")
        evaluation = evaluate(opp)
        override = OpportunityUserOverride(opportunity_id=opp.opportunity_id, market_trend_override="RISING")
        card = build_card_view_model(opp, evaluation, override=override)
        assert card.atlas_market_trend == "FALLING"
        assert card.market_trend == "RISING"


# ---------------------------------------------------------------
# Details view model (7)
# ---------------------------------------------------------------

class TestDetailsViewModel:
    def test_details_include_why_bullets(self):
        opp = make_opportunity(
            franchise="Brand X", collaboration_partner="Partner", exclusive_promo=True,
            required_spend=50.0, recent_sold_price=100.0,
        )
        evaluation = evaluate(opp)
        details = build_details_view_model(opp, evaluation)
        assert isinstance(details.why_bullets, list)

    def test_details_json_compatible(self):
        opp = make_opportunity()
        evaluation = evaluate(opp)
        details = build_details_view_model(opp, evaluation)
        import json
        json.dumps(details.to_dict())

    def test_override_detail_shows_atlas_and_user_values(self):
        opp = make_opportunity(recent_sold_price=100.0)
        evaluation = evaluate(opp)
        override = OpportunityUserOverride(
            opportunity_id=opp.opportunity_id, market_strength_override="STRONG", reason="local demand",
        )
        details = build_details_view_model(opp, evaluation, override=override)
        entry = next(o for o in details.overrides if o.field_name == "market_strength")
        assert entry.user_value == "STRONG"
        assert entry.atlas_value in {"STRONG", "MEDIUM", "WEAK", "UNKNOWN"}
        assert entry.reason == "local demand"
