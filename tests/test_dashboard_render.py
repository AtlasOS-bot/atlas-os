"""
Atlas v21 - Module 8: dashboard HTML rendering tests.
"""

from collector_intelligence.dashboard_render import (
    render_dashboard_page,
    render_demand_tags,
    render_heart_button,
    render_links,
    render_opportunity_card,
)
from collector_intelligence.dashboard_view import (
    ImageViewModel,
    LinkViewModel,
    build_card_view_model,
    build_details_view_model,
)
from collector_intelligence.decision_engine import evaluate_opportunity
from collector_intelligence.models import CollectorOpportunity


def make_card(**overrides):
    fields = {"product_name": "Test Product", "brand": "Brand X"}
    fields.update(overrides)
    opp = CollectorOpportunity(**fields)
    evaluation = evaluate_opportunity(opp)
    return build_card_view_model(opp, evaluation), opp, evaluation


class TestCardRendering:
    def test_renders_product_name(self):
        card, _, _ = make_card(product_name="Brand X Collab Item")
        html = render_opportunity_card(card)
        assert "Brand X Collab Item" in html

    def test_renders_market_strength_badge_with_text_not_just_color(self):
        card, _, _ = make_card()
        html = render_opportunity_card(card)
        assert card.market_strength in html
        assert 'aria-label="Market strength:' in html

    def test_renders_confidence_separately(self):
        card, _, _ = make_card()
        html = render_opportunity_card(card)
        assert 'aria-label="Confidence:' in html

    def test_no_buy_hold_watch_pass_language(self):
        import re
        card, _, _ = make_card(recent_sold_price=100.0, required_spend=50.0)
        html = render_opportunity_card(card)
        for forbidden in ("BUY", "HOLD", "WATCH", "PASS", "CONDITIONAL BUY", "STRONG WATCH"):
            assert re.search(rf"\b{forbidden}\b", html.upper()) is None

    def test_no_long_sentences_on_card(self):
        card, _, _ = make_card(exclusive_promo=True, event_exclusive=True)
        html = render_opportunity_card(card)
        # demand tags section should contain only short <li> tags, no
        # paragraph-length text blocks
        import re
        tag_texts = re.findall(r'<li class="tag">([^<]+)</li>', html)
        for text in tag_texts:
            assert len(text) < 30

    def test_demand_tags_capped_at_three_in_markup(self):
        card, _, _ = make_card(
            exclusive_promo=True, event_exclusive=True, sealed_product=True,
            artist_name="Artist", character_names=["Hero"],
        )
        html = render_demand_tags(card.demand_tags)
        assert html.count("<li") <= 3

    def test_details_panel_collapsed_by_default(self):
        card, opp, evaluation = make_card(
            franchise="Brand X", collaboration_partner="Partner",
            required_spend=50.0, recent_sold_price=100.0,
        )
        details = build_details_view_model(opp, evaluation)
        html = render_opportunity_card(card, details)
        assert "<details" in html
        assert "open" not in html.split("<details", 1)[1].split(">", 1)[0]

    def test_view_product_link_rendered_when_available(self):
        card, _, _ = make_card(purchase_url="https://example.test/buy")
        html = render_opportunity_card(card)
        assert 'href="https://example.test/buy"' in html
        assert "View Product" in html

    def test_ebay_sold_hidden_when_unavailable(self):
        card, _, _ = make_card()
        html = render_opportunity_card(card)
        assert "eBay Sold" not in html

    def test_links_open_safely_in_new_tab(self):
        card, _, _ = make_card(purchase_url="https://example.test/buy")
        html = render_opportunity_card(card)
        assert 'rel="noopener noreferrer"' in html

    def test_notes_and_edit_buttons_always_present(self):
        card, _, _ = make_card()
        html = render_opportunity_card(card)
        assert 'data-action="notes"' in html
        assert 'data-action="edit"' in html

    def test_manual_override_badge_shown_when_overridden(self):
        card, opp, evaluation = make_card()
        from collector_intelligence.dashboard_models import OpportunityUserOverride
        override = OpportunityUserOverride(opportunity_id=opp.opportunity_id, market_strength_override="STRONG")
        card_with_override = build_card_view_model(opp, evaluation, override=override)
        html = render_opportunity_card(card_with_override)
        assert "Manual override" in html

    def test_no_override_badge_when_not_overridden(self):
        card, _, _ = make_card()
        html = render_opportunity_card(card)
        assert "Manual override" not in html

    def test_complete_set_caution_badge_shown(self):
        card, _, _ = make_card(
            recent_sold_price=2200.0,
            risks=["This resale figure reflects a complete set, not a single item."],
        )
        html = render_opportunity_card(card)
        assert "Complete-set pricing" in html


class TestXSSSafety:
    def test_product_name_escaped(self):
        card, _, _ = make_card(product_name="<script>alert(1)</script>")
        html = render_opportunity_card(card)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_demand_tag_escaped(self):
        html = render_demand_tags(["<img src=x onerror=alert(1)>"])
        assert "<img src=x" not in html
        assert "&lt;img" in html

    def test_image_alt_text_escaped(self):
        image = ImageViewModel(url="https://example.test/x.jpg", alt_text='"><script>x</script>', source_label=None, is_placeholder=False)
        card, _, _ = make_card()
        card.image = image
        html = render_opportunity_card(card)
        assert "<script>x</script>" not in html


class TestHeartButton:
    def test_empty_heart_when_not_hearted(self):
        html = render_heart_button("opp-1", hearted=False)
        assert 'aria-pressed="false"' in html
        assert "Save to Hearted Items" in html
        assert "♡" in html

    def test_filled_heart_when_hearted(self):
        html = render_heart_button("opp-1", hearted=True)
        assert 'aria-pressed="true"' in html
        assert "Remove from Hearted Items" in html
        assert "♥" in html

    def test_heart_button_is_a_real_button_element(self):
        html = render_heart_button("opp-1", hearted=False)
        assert html.strip().startswith("<button")

    def test_heart_button_has_accessible_label_not_relying_on_glyph_alone(self):
        html = render_heart_button("opp-1", hearted=False)
        assert "aria-label=" in html


class TestLinksRendering:
    def test_unavailable_link_omitted(self):
        links = {"product": LinkViewModel(label="View Product", url=None, available=False)}
        html = render_links(links)
        assert html == ""

    def test_available_link_rendered(self):
        links = {"product": LinkViewModel(label="View Product", url="https://example.test/x", available=True)}
        html = render_links(links)
        assert "https://example.test/x" in html


class TestPageRendering:
    def test_empty_state_when_no_cards(self):
        html = render_dashboard_page([])
        assert "No opportunities" in html

    def test_renders_multiple_cards(self):
        card_a, _, _ = make_card(product_name="Item A")
        card_b, _, _ = make_card(product_name="Item B")
        html = render_dashboard_page([card_a, card_b])
        assert "Item A" in html
        assert "Item B" in html

    def test_page_links_to_hearted_items(self):
        html = render_dashboard_page([])
        assert "hearted.html" in html
        assert "Hearted Items" in html

    def test_page_references_stylesheet_and_script(self):
        html = render_dashboard_page([])
        assert 'href="styles.css"' in html
        assert 'src="app.js"' in html

    def test_page_is_deterministic(self):
        card, _, _ = make_card()
        html_a = render_dashboard_page([card])
        html_b = render_dashboard_page([card])
        assert html_a == html_b

    def test_opportunities_page_has_drawer_container(self):
        # Notes/Edit buttons on this page need somewhere to open into.
        html = render_dashboard_page([])
        assert 'id="drawer"' in html
        assert 'id="drawer-body"' in html

    def test_opportunities_page_has_manual_item_template(self):
        # "+ Add Item" in the nav must work from either page.
        html = render_dashboard_page([])
        assert 'id="manual-item-form-template"' in html

    def test_nav_has_all_drops_hearted_items_and_add_item(self):
        html = render_dashboard_page([])
        assert "All Drops" in html
        assert "Hearted Items" in html
        assert 'id="nav-add-item"' in html
        assert "+ Add Item" in html
