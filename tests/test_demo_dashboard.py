"""
Atlas v21 - Module 8: DEMO dataset and demo-mode rendering tests.

Covers two things that matter most for a demo dataset: it must never
be mistakable for live data, and it must never leak into the default
(live) rendering path.
"""

import re

from collector_intelligence.dashboard_models import HeartedItem
from collector_intelligence.dashboard_render import render_dashboard_page, render_hearted_items_page
from collector_intelligence.dashboard_view import build_card_view_model, build_details_view_model, build_hearted_item_row
from collector_intelligence.decision_engine import evaluate_opportunity
from collector_intelligence.demo_fixtures import (
    DEMO_ID_PREFIX, build_demo_hearted_items, build_demo_images,
    build_demo_links, build_demo_opportunities, build_demo_overrides,
)


def build_demo_cards():
    opportunities = build_demo_opportunities()
    images = build_demo_images()
    links = build_demo_links()
    overrides = build_demo_overrides()

    cards = []
    for opp in opportunities:
        evaluation = evaluate_opportunity(opp)
        cards.append(build_card_view_model(
            opp, evaluation,
            override=overrides.get(opp.opportunity_id),
            image_record=images.get(opp.opportunity_id),
            user_links=links.get(opp.opportunity_id),
        ))
    return cards, opportunities


class TestDemoFixtureIntegrity:
    def test_exactly_eight_demo_opportunities(self):
        assert len(build_demo_opportunities()) == 8

    def test_every_demo_opportunity_id_is_prefixed(self):
        for opp in build_demo_opportunities():
            assert opp.opportunity_id.startswith(DEMO_ID_PREFIX)

    def test_ids_are_unique(self):
        ids = [opp.opportunity_id for opp in build_demo_opportunities()]
        assert len(ids) == len(set(ids))

    def test_every_demo_opportunity_has_an_image_record(self):
        images = build_demo_images()
        for opp in build_demo_opportunities():
            assert opp.opportunity_id in images
            assert images[opp.opportunity_id].primary_image_url

    def test_every_demo_opportunity_has_an_ebay_sold_link(self):
        links = build_demo_links()
        for opp in build_demo_opportunities():
            owned = links.get(opp.opportunity_id, [])
            assert any(link.link_type == "ebay_sold" for link in owned)

    def test_every_demo_opportunity_has_a_product_link(self):
        for opp in build_demo_opportunities():
            assert opp.purchase_url

    def test_exactly_one_demo_override(self):
        overrides = build_demo_overrides()
        assert len(overrides) == 1
        opportunity_id = next(iter(overrides))
        assert opportunity_id.startswith(DEMO_ID_PREFIX)

    def test_demo_hearted_items_cover_both_manual_and_linked(self):
        items = build_demo_hearted_items()
        assert any(item.opportunity_id is not None for item in items)
        assert any(item.is_manual() for item in items)

    def test_demo_market_strengths_are_computed_not_hardcoded(self):
        # Spot check: strengths differ across items, proving they come
        # from the real classifier rather than a fixed string.
        cards, _ = build_demo_cards()
        strengths = {card.market_strength for card in cards}
        assert len(strengths) > 1


class TestDemoCardRendering:
    def test_no_buy_hold_watch_pass_language(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards, demo=True)
        for forbidden in ("BUY", "HOLD", "WATCH", "PASS", "CONDITIONAL BUY"):
            assert re.search(rf"\b{forbidden}\b", html.upper()) is None

    def test_demand_tags_capped_at_three(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards, demo=True)
        for tag_block in re.findall(r'<ul class="demand-tags"[^>]*>(.*?)</ul>', html):
            assert tag_block.count("<li") <= 3

    def test_overridden_card_shows_manual_override_badge(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards, demo=True)
        assert "Manual override" in html

    def test_unknown_strength_item_present(self):
        cards, _ = build_demo_cards()
        strengths = {card.market_strength for card in cards}
        assert "UNKNOWN" in strengths


class TestDemoBanner:
    def test_demo_dashboard_page_shows_banner(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards, demo=True)
        assert "DEMO DATA" in html
        assert "demo-banner" in html

    def test_live_dashboard_page_has_no_banner(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards, demo=False)
        assert "DEMO DATA" not in html
        assert "demo-banner" not in html

    def test_default_is_live_not_demo(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards)
        assert "DEMO DATA" not in html

    def test_demo_hearted_items_page_shows_banner(self):
        html = render_hearted_items_page([], demo=True)
        assert "DEMO DATA" in html

    def test_live_hearted_items_page_has_no_banner(self):
        html = render_hearted_items_page([])
        assert "DEMO DATA" not in html

    def test_demo_nav_links_to_demo_pages(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards, demo=True)
        assert 'href="demo-index.html"' in html
        assert 'href="demo-hearted.html"' in html

    def test_live_nav_links_to_live_pages(self):
        cards, _ = build_demo_cards()
        html = render_dashboard_page(cards, demo=False)
        assert 'href="index.html"' in html
        assert 'href="hearted.html"' in html
        assert "demo-index.html" not in html


class TestDemoHeartedItemsRendering:
    def test_manual_and_linked_rows_render(self):
        items = build_demo_hearted_items()
        _, opportunities = build_demo_cards()
        opportunities_by_id = {opp.opportunity_id: opp for opp in opportunities}

        rows = []
        for item in items:
            opportunity = opportunities_by_id.get(item.opportunity_id) if item.opportunity_id else None
            evaluation = evaluate_opportunity(opportunity) if opportunity else None
            rows.append(build_hearted_item_row(item, opportunity=opportunity, evaluation=evaluation))

        html = render_hearted_items_page(rows, demo=True)
        assert "Pitch Black ETB" in html
        assert "Vintage Charizard" in html
        assert "Manual" in html
