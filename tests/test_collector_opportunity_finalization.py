"""
Atlas v21 - Module 4: Collector Opportunity Aggregation and
Finalization.

Tests finalize_collector_opportunity() / finalize_collector_
opportunities() end-to-end against real RawSourceInput fixtures -
no network access, no database. Assertions favor actual outputs
(dispositions, conflicts, resolved field values) over mocking.
"""

import random

from collector_intelligence.aggregation_config import FinalizationConfig
from collector_intelligence.aggregator import build_candidates, merge_group
from collector_intelligence.finalization import (
    finalize_collector_opportunities,
    finalize_collector_opportunity,
)
from collector_intelligence.finalized_summary import summarize_finalized_opportunity
from collector_intelligence.identity_matching import group_drafts, same_opportunity
from collector_intelligence.models import CollectorOpportunity
from collector_intelligence.source_models import RawSourceInput


# ---------------------------------------------------------------
# Round1 required scenario fixtures
# ---------------------------------------------------------------

def round1_five_sources():
    return [
        RawSourceInput(
            title="ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN",
            body=(
                "One Piece and Round1 launched a limited collaboration "
                "campaign. Customers who spend $200 on eligible arcade play "
                "receive four exclusive promotional card packs. The "
                "campaign runs at participating Round1 locations for a "
                "limited time. Official print quantity has not been "
                "disclosed."
            ),
            source_type="OFFICIAL",
            source_name="Round1 Newsroom",
        ),
        RawSourceInput(
            title="ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN",
            body=(
                "The One Piece x Round1 collaboration campaign is now live "
                "at participating Round1 locations. Limit 1 per customer."
            ),
            source_type="RETAILER",
            source_name="Round1 Store Update",
        ),
        RawSourceInput(
            title="Collectors report Round1 packs selling out fast",
            body=(
                "One Piece x Round1 promotional packs are reportedly "
                "selling out quickly, with strong collector demand across "
                "social media."
            ),
            source_type="COMMUNITY",
            source_name="TCG Forum",
        ),
        RawSourceInput(
            title="Marketplace watch: One Piece Round1 complete sets",
            body=(
                "One Piece x Round1 promotional cards were part of a "
                "recent collaboration. A complete promo set reportedly "
                "sold for approximately $2,200 on the secondary market."
            ),
            source_type="MARKETPLACE",
            source_name="Resale Tracker",
        ),
        RawSourceInput(
            title="Is one pack worth $2200?",
            body=(
                "One Piece x Round1 collaboration: a single promotional "
                "pack alone is reportedly sold for $2,200 on the resale "
                "market."
            ),
            source_type="SOCIAL",
            source_name="Random Poster",
        ),
    ]


def round1_official_and_marketplace():
    return [
        RawSourceInput(
            title="ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN",
            body=(
                "One Piece and Round1 launched a limited collaboration "
                "campaign. Customers who spend $200 on eligible arcade "
                "play receive four exclusive promotional card packs. The "
                "campaign runs at participating Round1 locations for a "
                "limited time."
            ),
            source_type="OFFICIAL",
            source_name="Round1 Newsroom",
        ),
        RawSourceInput(
            title="Marketplace watch: One Piece Round1 complete sets",
            body=(
                "One Piece x Round1 promotional cards were part of a "
                "recent collaboration. A complete promo set reportedly "
                "sold for approximately $2,200 on the secondary market."
            ),
            source_type="MARKETPLACE",
            source_name="Resale Tracker",
        ),
    ]


def round1_verified_followup():
    return [
        RawSourceInput(
            title=(
                "ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN — COMPLETE "
                "SET CONFIRMED"
            ),
            body=(
                "One Piece x Round1 collaboration is now confirmed as a "
                "complete promo set. It sold for $2,200 in a confirmed "
                "marketplace transaction."
            ),
            source_type="MARKETPLACE",
            source_name="Resale Tracker Verified",
        ),
    ]


class TestRound1RequiredScenario:
    def test_all_five_sources_processed(self):
        result = finalize_collector_opportunity(round1_five_sources())
        assert len(result.source_results) == 5

    def test_all_five_sources_accepted(self):
        result = finalize_collector_opportunity(round1_five_sources())
        assert len(result.accepted_sources) == 5
        assert len(result.rejected_sources) == 0

    def test_official_identity_and_rules_win(self):
        result = finalize_collector_opportunity(round1_five_sources())
        assert result.opportunity.collaboration_partner == "Round1"
        assert result.opportunity.franchise == "One Piece"
        assert result.opportunity.required_spend == 200.0

    def test_community_demand_is_supporting_not_authoritative(self):
        result = finalize_collector_opportunity(round1_five_sources())
        community = next(
            s for s in result.accepted_sources if s.source_name == "TCG Forum"
        )
        assert community.disposition in {
            "ACCEPTED_SUPPORTING", "ACCEPTED_STATUS_UPDATE",
        }

    def test_marketplace_populates_resale_conservatively(self):
        result = finalize_collector_opportunity(round1_five_sources())
        assert result.opportunity.recent_sold_price == 2200.0

    def test_unit_scope_conflict_is_recorded(self):
        result = finalize_collector_opportunity(round1_five_sources())
        scope_conflicts = [
            c for c in result.conflicts
            if c.field_name == "recent_sold_price"
            and "unit" in c.explanation.lower()
        ]
        assert scope_conflicts
        assert scope_conflicts[0].requires_manual_review

    def test_weak_incorrect_claim_does_not_silently_win(self):
        # The social source's incorrect "one pack = $2,200" claim must
        # not become the unchallenged truth - it must surface as a
        # conflict, not silently overwrite the marketplace reading.
        result = finalize_collector_opportunity(round1_five_sources())
        assert any(
            c.field_name == "recent_sold_price" and c.requires_manual_review
            for c in result.conflicts
        )

    def test_manual_review_required(self):
        result = finalize_collector_opportunity(round1_five_sources())
        assert result.requires_manual_review is True
        assert result.manual_review_reasons

    def test_recommendation_is_not_blindly_critical_buy(self):
        result = finalize_collector_opportunity(round1_five_sources())
        assert result.evaluation.recommendation != "CRITICAL_BUY"

    def test_evidence_ledger_explains_every_value(self):
        result = finalize_collector_opportunity(round1_five_sources())
        spend_evidence = [
            e for e in result.evidence_ledger if e.field_name == "required_spend"
        ]
        assert spend_evidence
        assert spend_evidence[0].proposed_value == 200.0
        assert spend_evidence[0].source_name == "Round1 Newsroom"

    def test_complete_set_warning_in_summary(self):
        result = finalize_collector_opportunity(round1_five_sources())
        summary = summarize_finalized_opportunity(result)
        assert "complete set" in summary.lower()

    def test_summary_shows_recommendation_and_strategy(self):
        result = finalize_collector_opportunity(round1_five_sources())
        summary = summarize_finalized_opportunity(result)
        assert "Recommendation:" in summary
        assert "Strategy:" in summary
        assert "Manual review:" in summary


class TestRound1MismatchThenResolved:
    def test_first_round_has_mismatch_and_watch(self):
        result = finalize_collector_opportunity(round1_official_and_marketplace())
        assert result.evaluation.recommendation == "WATCH"
        assert any("complete set" in w.lower() for w in result.evaluation.warnings)

    def test_second_round_resolves_mismatch(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        second = finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        assert any(
            c.field_name == "complete_set_mismatch" and c.new_value is False
            for c in second.change_summary
        )

    def test_confidence_increases_after_verification(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        second = finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        assert second.evaluation.confidence_score > first.evaluation.confidence_score

    def test_risk_decreases_after_verification(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        second = finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        assert second.evaluation.risk_score < first.evaluation.risk_score

    def test_recommendation_improves(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        second = finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        assert second.evaluation.recommendation != first.evaluation.recommendation

    def test_change_summary_explains_the_change(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        second = finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        recommendation_change = next(
            c for c in second.change_summary if c.field_name == "recommendation"
        )
        assert recommendation_change.material_change is True

    def test_original_opportunity_not_mutated_across_rounds(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        before = first.opportunity.to_dict()
        finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        assert first.opportunity.to_dict() == before

    def test_history_accumulates_across_rounds(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        second = finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        assert len(second.opportunity.evidence) > len(first.opportunity.evidence)


# ---------------------------------------------------------------
# Source authority (scenarios 4, 5, 6, 7, 45, 46)
# ---------------------------------------------------------------

class TestSourceAuthority:
    def test_official_beats_community_for_identity(self):
        official = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration called "
                 "the Deluxe Anniversary Edition.",
            source_type="OFFICIAL",
            source_name="Brand X Newsroom",
        )
        community = RawSourceInput(
            title="Brand X thing",
            body="Brand X and Partner Co dropped something cool recently.",
            source_type="COMMUNITY",
            source_name="Forum Post",
        )
        result = finalize_collector_opportunity([community, official])
        assert result.opportunity.product_name == "Brand X Official Product"

    def test_retailer_beats_social_for_retail_price(self):
        retailer = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. The "
                 "retail price is $60.",
            source_type="RETAILER",
            source_name="Official Store",
        )
        social = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. I heard "
                 "the retail price is $45.",
            source_type="SOCIAL",
            source_name="Rumor Account",
        )
        result = finalize_collector_opportunity([social, retailer])
        assert result.opportunity.retail_price == 60.0

    def test_marketplace_accepted_only_for_market_evidence(self):
        sources = round1_five_sources()
        candidates = build_candidates(sources)
        marketplace = next(
            c for c in candidates if c.source.source_name == "Resale Tracker"
        )
        assert marketplace.disposition == "ACCEPTED_MARKET_EVIDENCE"

    def test_asking_price_does_not_become_confirmed_sold(self):
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. One "
                 "seller is asking $900 for their copy.",
            source_type="MARKETPLACE",
            source_name="Listing Watch",
        )
        result = finalize_collector_opportunity([source])
        assert result.opportunity.recent_sold_price is None

    def test_multiple_consistent_sold_observations(self):
        sources = [
            RawSourceInput(
                title="Brand X Item",
                body=f"Brand X and Partner Co launched a collaboration. "
                     f"A copy sold for ${price}.",
                source_type="MARKETPLACE",
                source_name=f"Tracker {price}",
            )
            for price in (198, 205, 202)
        ]
        result = finalize_collector_opportunity(sources)
        assert result.opportunity.recent_sold_price == 202.0

    def test_extreme_sold_price_outlier_excluded(self):
        sources = [
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. A "
                     "copy sold for $200.",
                source_type="MARKETPLACE",
                source_name="Tracker A",
            ),
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. A "
                     "copy sold for $210.",
                source_type="MARKETPLACE",
                source_name="Tracker B",
            ),
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. A "
                     "copy sold for $50000.",
                source_type="MARKETPLACE",
                source_name="Tracker Outlier",
            ),
        ]
        result = finalize_collector_opportunity(sources)
        assert result.opportunity.recent_sold_price < 1000
        outlier_evidence = next(
            e for e in result.evidence_ledger
            if e.source_name == "Tracker Outlier" and e.field_name == "recent_sold_price"
        )
        assert outlier_evidence.accepted is False
        assert "outlier" in outlier_evidence.rejection_reason.lower()

    def test_source_recency_does_not_automatically_beat_authority(self):
        older_official = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration.",
            source_type="OFFICIAL",
            source_name="Official Newsroom",
            published_at="2026-01-01T00:00:00+00:00",
        )
        newer_social = RawSourceInput(
            title="Brand X thing everyone's talking about",
            body="Brand X and Partner Co dropped a thing.",
            source_type="SOCIAL",
            source_name="Late Poster",
            published_at="2026-06-01T00:00:00+00:00",
        )
        result = finalize_collector_opportunity([older_official, newer_social])
        assert result.opportunity.product_name == "Brand X Official Product"


# ---------------------------------------------------------------
# Unit scope: complete set / box / case / graded (scenarios 10, 11, 12)
# ---------------------------------------------------------------

class TestUnitScopeConflicts:
    def test_complete_set_vs_one_pack_conflict(self):
        result = finalize_collector_opportunity(round1_official_and_marketplace())
        assert any(
            c.field_name == "recent_sold_price" and "unit" in c.explanation.lower()
            for c in result.conflicts
        ) or any("complete set" in r.lower() for r in result.opportunity.risks)

    def test_box_vs_case_conflict(self):
        sources = [
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. A "
                     "booster box sold for $150.",
                source_type="MARKETPLACE",
                source_name="Box Watch",
            ),
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. A "
                     "sealed case sold for $1500.",
                source_type="MARKETPLACE",
                source_name="Case Watch",
            ),
        ]
        result = finalize_collector_opportunity(sources)
        scope_conflict = next(
            (c for c in result.conflicts if c.field_name == "recent_sold_price"
             and set(c.competing_values) >= {"box", "case"}),
            None,
        )
        assert scope_conflict is not None
        assert scope_conflict.requires_manual_review

    def test_graded_vs_ungraded_conflict(self):
        sources = [
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. A "
                     "graded PSA 10 copy sold for $500.",
                source_type="MARKETPLACE",
                source_name="Grader Watch",
            ),
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. An "
                     "ungraded raw copy sold for $120.",
                source_type="MARKETPLACE",
                source_name="Raw Watch",
            ),
        ]
        result = finalize_collector_opportunity(sources)
        grading_conflict = next(
            (c for c in result.conflicts
             if c.field_name == "recent_sold_price"
             and set(c.competing_values) >= {"graded", "ungraded"}),
            None,
        )
        assert grading_conflict is not None
        assert grading_conflict.requires_manual_review

    def test_missing_unit_scope_requires_manual_review(self):
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. A copy "
                 "sold for $75.",
            source_type="MARKETPLACE",
            source_name="Vague Tracker",
        )
        result = finalize_collector_opportunity([source])
        assert any(
            "unit scope" in reason.lower()
            for reason in result.manual_review_reasons
        )


# ---------------------------------------------------------------
# Boolean negation (scenario 13)
# ---------------------------------------------------------------

class TestBooleanNegation:
    def test_official_negation_beats_community_limited_claim(self):
        official = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration. This "
                 "product is not limited.",
            source_type="OFFICIAL",
            source_name="Brand X Newsroom",
        )
        community = RawSourceInput(
            title="Brand X thing",
            body="Brand X and Partner Co launched a collaboration. Super "
                 "limited drop, get it now!",
            source_type="COMMUNITY",
            source_name="Hype Forum",
        )
        result = finalize_collector_opportunity([community, official])
        assert result.opportunity.limited_quantity is False


# ---------------------------------------------------------------
# Rumors (scenarios 14, 15)
# ---------------------------------------------------------------

class TestRumors:
    def test_rumor_remains_rumor_after_repeated_weak_reports(self):
        sources = [
            RawSourceInput(
                title="Rumor: Brand X x Partner Co coming soon",
                body="Rumor has it Brand X and Partner Co may release a "
                     "collaboration soon.",
                source_type="SOCIAL",
                source_name=f"Poster {i}",
            )
            for i in range(3)
        ]
        result = finalize_collector_opportunity(sources)
        assert all(
            s.disposition == "ACCEPTED_RUMOR" for s in result.accepted_sources
        )
        assert result.evaluation.recommendation in {"WATCH", "SKIP", "AVOID"}

    def test_rumor_becomes_confirmed_after_official_announcement(self):
        rumor = RawSourceInput(
            title="Rumor: Brand X x Partner Co coming soon",
            body="Rumor has it Brand X and Partner Co may release a "
                 "collaboration soon.",
            source_type="SOCIAL",
            source_name="Early Leaker",
        )
        first = finalize_collector_opportunity([rumor])

        official = RawSourceInput(
            title="Brand X x Partner Co Official Collaboration",
            body="Brand X and Partner Co officially launched a "
                 "collaboration campaign today.",
            source_type="OFFICIAL",
            source_name="Brand X Newsroom",
        )
        second = finalize_collector_opportunity(
            [official], existing_opportunity=first.opportunity,
        )
        assert second.opportunity.status != "rumored"


# ---------------------------------------------------------------
# Status history (scenarios 16, 17, 18)
# ---------------------------------------------------------------

class TestStatusHistory:
    def test_sold_out_followed_by_restock(self):
        sources = [
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. The "
                     "item is sold out everywhere.",
                source_type="RETAILER",
                source_name="Store Update 1",
                discovered_at="2026-01-01T00:00:00+00:00",
            ),
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. The "
                     "item was restocked overnight.",
                source_type="RETAILER",
                source_name="Store Update 2",
                discovered_at="2026-01-02T00:00:00+00:00",
            ),
        ]
        result = finalize_collector_opportunity(sources)
        assert result.opportunity.status == "restocked"
        history = result.opportunity.raw_metadata.get("status_history", [])
        statuses = [h["status"] for h in history]
        assert "sold_out" in statuses
        assert "restocked" in statuses

    def test_restock_followed_by_second_sellout(self):
        sources = [
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. The "
                     "item was restocked overnight.",
                source_type="RETAILER",
                source_name="Store Update 1",
                discovered_at="2026-01-01T00:00:00+00:00",
            ),
            RawSourceInput(
                title="Brand X Item",
                body="Brand X and Partner Co launched a collaboration. The "
                     "item is sold out again.",
                source_type="RETAILER",
                source_name="Store Update 2",
                discovered_at="2026-01-03T00:00:00+00:00",
            ),
        ]
        result = finalize_collector_opportunity(sources)
        assert result.opportunity.status == "sold_out"

    def test_stale_community_report_does_not_override_current_retailer_stock(self):
        community_sold_out = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. "
                 "Community reports say it's sold out.",
            source_type="COMMUNITY",
            source_name="Old Forum Post",
            discovered_at="2026-01-01T00:00:00+00:00",
        )
        retailer_in_stock = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. It is "
                 "available now at the official store.",
            source_type="RETAILER",
            source_name="Current Store Status",
            discovered_at="2026-01-05T00:00:00+00:00",
        )
        result = finalize_collector_opportunity(
            [community_sold_out, retailer_in_stock]
        )
        assert result.opportunity.status == "live"


# ---------------------------------------------------------------
# Dates (scenarios 19, 20)
# ---------------------------------------------------------------

class TestDates:
    def test_conflicting_official_release_dates_flagged(self):
        first = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration. The "
                 "product releases July 20.",
            source_type="OFFICIAL",
            source_name="Official Newsroom A",
        )
        second = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration. The "
                 "product releases August 4.",
            source_type="OFFICIAL",
            source_name="Official Newsroom B",
        )
        result = finalize_collector_opportunity([first, second])
        assert any(
            c.field_name == "release_date" for c in result.conflicts
        )

    def test_announcement_and_release_dates_stay_separate(self):
        source = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co announced a collaboration on "
                 "July 1. The product releases July 20.",
            source_type="OFFICIAL",
            source_name="Official Newsroom",
        )
        result = finalize_collector_opportunity([source])
        assert result.opportunity.announcement_date is not None
        assert result.opportunity.release_date is not None
        assert result.opportunity.announcement_date != result.opportunity.release_date


# ---------------------------------------------------------------
# Product identity / variants (scenarios 21-25)
# ---------------------------------------------------------------

class TestIdentityAndVariants:
    def test_different_regional_prices_flagged(self):
        us_price = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration. US "
                 "retail price is $60.",
            source_type="OFFICIAL",
            source_name="US Newsroom",
        )
        eu_price = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration. EU "
                 "retail price is $85.",
            source_type="OFFICIAL",
            source_name="EU Newsroom",
        )
        result = finalize_collector_opportunity([us_price, eu_price])
        assert any(c.field_name == "retail_price" for c in result.conflicts)

    def test_different_product_variants_remain_separate(self):
        pack = build_candidates([RawSourceInput(
            title="One Piece x Round1 Promotional Pack",
            body="One Piece and Round1 launched a limited collaboration "
                 "for a promotional pack.",
            source_type="OFFICIAL",
        )])[0].draft
        box = build_candidates([RawSourceInput(
            title="One Piece Booster Box",
            body="A new One Piece booster box is now available at retail.",
            source_type="RETAILER",
        )])[0].draft
        assert not same_opportunity(pack, box)

    def test_same_opportunity_differently_worded_names_merge(self):
        a = RawSourceInput(
            title="ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN",
            body="One Piece and Round1 launched a limited collaboration "
                 "campaign for exclusive promotional packs.",
            source_type="OFFICIAL",
        )
        b = RawSourceInput(
            title="Round1's One Piece Promo Pack Drop",
            body="One Piece x Round1 promotional packs are now available "
                 "at Round1 locations.",
            source_type="RETAILER",
        )
        candidates = build_candidates([a, b])
        drafts = [c.draft for c in candidates]
        groups = group_drafts(drafts)
        assert len(groups) == 1

    def test_same_franchise_different_products_do_not_merge(self):
        result = finalize_collector_opportunities([
            RawSourceInput(
                title="One Piece x Round1 Promotional Pack",
                body="One Piece and Round1 launched a limited "
                     "collaboration for a promotional pack.",
                source_type="OFFICIAL",
            ),
            RawSourceInput(
                title="One Piece Tournament Promo Card",
                body="One Piece and Regional Championship launched a "
                     "tournament promo collaboration.",
                source_type="OFFICIAL",
            ),
        ])
        assert result.group_count == 2

    def test_product_name_becomes_more_specific_after_official_source(self):
        vague = RawSourceInput(
            title="One Piece x Round1",
            body="One Piece and Round1 launched a limited collaboration.",
            source_type="COMMUNITY",
        )
        first = finalize_collector_opportunity([vague])

        specific = RawSourceInput(
            title="ONE PIECE x ROUND1 SUMMER CAMPAIGN PROMOTIONAL CARD PACK",
            body="One Piece and Round1 launched a limited collaboration.",
            source_type="OFFICIAL",
        )
        second = finalize_collector_opportunity(
            [specific], existing_opportunity=first.opportunity,
        )
        assert second.opportunity.product_name == (
            "ONE PIECE x ROUND1 SUMMER CAMPAIGN PROMOTIONAL CARD PACK"
        )


# ---------------------------------------------------------------
# Existing opportunity handling (scenarios 26-30)
# ---------------------------------------------------------------

class TestExistingOpportunityUpdate:
    def test_existing_opportunity_not_mutated(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        before = first.opportunity.to_dict()
        finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        assert first.opportunity.to_dict() == before

    def test_existing_manual_field_is_preserved_by_default(self):
        existing = CollectorOpportunity(
            product_name="Manually Verified Product Name",
            brand="Brand X",
            retail_price=59.99,
        )
        new_source = RawSourceInput(
            title="Brand X Item Restock",
            body="Brand X and Partner Co product is back. The retail "
                 "price is $45.",
            source_type="RETAILER",
        )
        result = finalize_collector_opportunity(
            [new_source], existing_opportunity=existing,
        )
        assert result.opportunity.retail_price == 59.99

    def test_allow_manual_overwrite_config_permits_update(self):
        existing = CollectorOpportunity(
            product_name="Manually Verified Product Name",
            brand="Brand X",
            retail_price=59.99,
        )
        new_source = RawSourceInput(
            title="Brand X Item Restock",
            body="Brand X and Partner Co product is back. The retail "
                 "price is $45.",
            source_type="RETAILER",
        )
        config = FinalizationConfig(allow_manual_value_overwrite=True)
        result = finalize_collector_opportunity(
            [new_source], existing_opportunity=existing, finalization_config=config,
        )
        assert result.opportunity.retail_price == 45.0

    def test_material_recommendation_change_in_change_summary(self):
        first = finalize_collector_opportunity(round1_official_and_marketplace())
        second = finalize_collector_opportunity(
            round1_verified_followup(), existing_opportunity=first.opportunity,
        )
        recommendation_changes = [
            c for c in second.change_summary
            if c.field_name == "recommendation" and c.material_change
        ]
        assert recommendation_changes

    def test_small_formatting_change_not_in_change_summary(self):
        existing = CollectorOpportunity(
            product_name="Brand X Item",
            brand="Brand X",
            franchise="Brand X",
        )
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration.",
            source_type="OFFICIAL",
        )
        result = finalize_collector_opportunity(
            [source], existing_opportunity=existing,
        )
        assert not any(
            c.field_name in {"created_at", "updated_at", "opportunity_id"}
            for c in result.change_summary
        )

    def test_dedup_key_change_is_reported(self):
        existing = CollectorOpportunity(
            product_name="Brand X Original Name",
            brand="Brand X",
            franchise="Brand X",
        )
        source = RawSourceInput(
            title="Brand X Totally Different Collaboration",
            body="Brand X and Different Partner launched a new "
                 "collaboration.",
            source_type="OFFICIAL",
        )
        config = FinalizationConfig(allow_manual_value_overwrite=True)
        result = finalize_collector_opportunity(
            [source], existing_opportunity=existing, finalization_config=config,
        )
        assert result.previous_dedup_key != result.current_dedup_key


# ---------------------------------------------------------------
# Extreme claims capped (scenario 32)
# ---------------------------------------------------------------

class TestExtremeClaims:
    def test_extreme_resale_claim_from_weak_source_is_flagged(self):
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. "
                 "Customers spend $20 to participate. I heard a copy sold "
                 "for $5,000!",
            source_type="SOCIAL",
            source_name="Hype Account",
        )
        result = finalize_collector_opportunity([source])
        assert any(
            "extreme" in reason.lower() for reason in result.manual_review_reasons
        )


# ---------------------------------------------------------------
# Source dispositions and rejection (scenarios 33, 34, 39)
# ---------------------------------------------------------------

class TestSourceDispositions:
    def test_irrelevant_source_is_rejected(self):
        source = RawSourceInput(
            title="Weather update",
            body="It will rain tomorrow in the local area.",
            source_type="NEWS",
        )
        candidates = build_candidates([source])
        assert candidates[0].disposition == "REJECTED_IRRELEVANT"

    def test_duplicate_source_is_rejected(self):
        source = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration.",
            source_type="OFFICIAL",
            source_url="https://example.com/brandx-announcement",
        )
        duplicate = RawSourceInput(
            title="Brand X Official Product",
            body="Brand X and Partner Co launched a collaboration.",
            source_type="OFFICIAL",
            source_url="https://example.com/brandx-announcement",
        )
        candidates = build_candidates([source, duplicate])
        assert candidates[1].disposition == "REJECTED_DUPLICATE"

    def test_every_source_receives_a_disposition(self):
        sources = round1_five_sources() + [
            RawSourceInput(title="Unrelated", body="Nothing collector-related here.")
        ]
        result = finalize_collector_opportunity(round1_five_sources())
        candidates = build_candidates(sources)
        assert len(candidates) == len(sources)
        assert all(c.disposition for c in candidates)


# ---------------------------------------------------------------
# Batch grouping (scenarios 35, 36)
# ---------------------------------------------------------------

class TestBatchGrouping:
    def test_batch_with_multiple_products_creates_multiple_groups(self):
        sources = [
            RawSourceInput(
                title="One Piece x Round1 Promotional Pack",
                body="One Piece and Round1 launched a limited "
                     "collaboration for a promotional pack.",
                source_type="OFFICIAL",
            ),
            RawSourceInput(
                title="One Piece Tournament Promo Card",
                body="One Piece and Regional Championship launched a "
                     "tournament promo collaboration.",
                source_type="OFFICIAL",
            ),
        ]
        result = finalize_collector_opportunities(sources)
        assert result.group_count == 2
        assert result.total_sources == 2
        assert result.accepted_source_count == 2

    def test_batch_result_totals_are_consistent(self):
        sources = round1_five_sources()
        result = finalize_collector_opportunities(sources)
        assert result.total_sources == len(sources)
        assert (
            result.accepted_source_count + result.rejected_source_count
            == result.total_sources
        )


# ---------------------------------------------------------------
# Evidence ledger completeness (scenarios 37, 38)
# ---------------------------------------------------------------

class TestEvidenceLedgerCompleteness:
    def test_ledger_contains_chosen_and_rejected_evidence(self):
        result = finalize_collector_opportunity(round1_five_sources())
        accepted = [e for e in result.evidence_ledger if e.accepted]
        rejected = [e for e in result.evidence_ledger if not e.accepted]
        assert accepted
        assert rejected

    def test_every_conflict_has_an_explanation(self):
        result = finalize_collector_opportunity(round1_five_sources())
        assert result.conflicts
        assert all(c.explanation for c in result.conflicts)


# ---------------------------------------------------------------
# Scoring integration (scenarios 40, 42)
# ---------------------------------------------------------------

class TestScoringIntegration:
    def test_final_score_comes_from_module_3(self):
        from collector_intelligence.decision_engine import evaluate_opportunity

        result = finalize_collector_opportunity(round1_five_sources())
        independent_eval = evaluate_opportunity(result.opportunity)
        assert result.evaluation.opportunity_score == independent_eval.opportunity_score
        assert result.evaluation.recommendation == independent_eval.recommendation

    def test_scores_remain_within_bounds(self):
        result = finalize_collector_opportunity(round1_five_sources())
        for field_name in (
            "collector_score", "flip_score", "hold_score", "scarcity_score",
            "demand_score", "hype_score", "acquisition_score", "risk_score",
            "confidence_score", "opportunity_score",
        ):
            value = getattr(result.evaluation, field_name)
            assert 0 <= value <= 100


# ---------------------------------------------------------------
# No mutation, no order dependency (scenarios 41, 45)
# ---------------------------------------------------------------

class TestNoMutationNoOrderDependency:
    def test_source_objects_not_mutated(self):
        sources = round1_five_sources()
        snapshots = [
            (s.title, s.body, s.source_type, s.source_name) for s in sources
        ]
        finalize_collector_opportunity(sources)
        after = [
            (s.title, s.body, s.source_type, s.source_name) for s in sources
        ]
        assert snapshots == after

    def test_result_is_order_independent(self):
        sources = round1_five_sources()
        forward = finalize_collector_opportunity(list(sources))

        shuffled = list(sources)
        random.Random(42).shuffle(shuffled)
        backward = finalize_collector_opportunity(shuffled)

        assert forward.opportunity.collaboration_partner == (
            backward.opportunity.collaboration_partner
        )
        assert forward.opportunity.required_spend == backward.opportunity.required_spend
        assert forward.opportunity.recent_sold_price == backward.opportunity.recent_sold_price
        assert forward.evaluation.recommendation == backward.evaluation.recommendation


# ---------------------------------------------------------------
# Summary formatter labeling (scenarios 43, 44)
# ---------------------------------------------------------------

class TestSummaryLabeling:
    def test_summary_labels_estimates_and_rumors(self):
        source = RawSourceInput(
            title="Rumor: Brand X x Partner Co coming soon",
            body="Rumor has it Brand X and Partner Co may release a "
                 "collaboration soon.",
            source_type="SOCIAL",
        )
        result = finalize_collector_opportunity([source])
        summary = summarize_finalized_opportunity(result)
        assert "RUMORED" in summary or "rumor" in summary.lower()

    def test_summary_displays_complete_set_warning(self):
        result = finalize_collector_opportunity(round1_official_and_marketplace())
        summary = summarize_finalized_opportunity(result)
        assert "complete set" in summary.lower()


# ---------------------------------------------------------------
# Field semantics: no cross-contamination (scenarios 47, 48, 49, 50)
# ---------------------------------------------------------------

class TestFieldSemantics:
    def test_purchase_limit_does_not_become_stated_quantity(self):
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. Limit "
                 "1 per customer.",
            source_type="RETAILER",
        )
        result = finalize_collector_opportunity([source])
        assert result.opportunity.purchase_limit == 1
        assert result.opportunity.stated_quantity is None

    def test_pack_quantity_does_not_become_purchase_limit(self):
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. "
                 "Customers receive four exclusive promotional packs.",
            source_type="OFFICIAL",
        )
        result = finalize_collector_opportunity([source])
        assert result.opportunity.purchase_limit is None
        assert result.opportunity.stated_quantity is None
        pack_note = [
            e for e in result.evidence_ledger if e.field_name == "pack_quantity_note"
        ]
        assert pack_note
        assert "4" in pack_note[0].proposed_value

    def test_required_spend_does_not_become_retail_price(self):
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration. "
                 "Customers who spend $200 on eligible purchases qualify.",
            source_type="OFFICIAL",
        )
        result = finalize_collector_opportunity([source])
        assert result.opportunity.required_spend == 200.0
        assert result.opportunity.retail_price is None

    def test_unknown_fields_remain_unknown(self):
        source = RawSourceInput(
            title="Brand X Item",
            body="Brand X and Partner Co launched a collaboration.",
            source_type="OFFICIAL",
        )
        result = finalize_collector_opportunity([source])
        assert result.opportunity.stated_quantity is None
        assert result.opportunity.recent_sold_price is None
        assert result.opportunity.release_date is None
