"""
Atlas v21 - Module 8: Hearted Items page tests (view model + rendering).
"""

from collector_intelligence.dashboard_models import HeartedItem
from collector_intelligence.dashboard_render import render_hearted_item_row, render_hearted_items_page
from collector_intelligence.dashboard_view import build_hearted_item_row
from collector_intelligence.decision_engine import evaluate_opportunity
from collector_intelligence.models import CollectorOpportunity


def make_opportunity(**overrides):
    fields = {"product_name": "Test Product", "brand": "Brand X"}
    fields.update(overrides)
    return CollectorOpportunity(**fields)


class TestHeartedItemRowViewModel:
    def test_manual_item_uses_its_own_fields(self):
        item = HeartedItem(
            product_name="Vintage Print", market_strength="MEDIUM",
            target_price=150.0, priority="high", image_url="https://example.test/x.jpg",
        )
        row = build_hearted_item_row(item)
        assert row.is_manual is True
        assert row.product_name == "Vintage Print"
        assert row.market_strength == "MEDIUM"
        assert row.image.url == "https://example.test/x.jpg"
        assert row.image.is_placeholder is False

    def test_manual_item_without_image_shows_placeholder(self):
        item = HeartedItem(product_name="No Image Item")
        row = build_hearted_item_row(item)
        assert row.image.is_placeholder is True

    def test_manual_item_requires_no_opportunity(self):
        item = HeartedItem(product_name="Fully manual")
        row = build_hearted_item_row(item)
        assert row.opportunity_id is None
        assert row.is_manual is True

    def test_atlas_linked_item_reuses_card_classification(self):
        opp = make_opportunity(recent_sold_price=100.0, required_spend=90.0)
        evaluation = evaluate_opportunity(opp)
        item = HeartedItem(opportunity_id=opp.opportunity_id)
        row = build_hearted_item_row(item, opportunity=opp, evaluation=evaluation)
        assert row.is_manual is False
        assert row.product_name == opp.product_name
        assert row.market_strength in {"STRONG", "MEDIUM", "WEAK", "UNKNOWN"}

    def test_target_price_formatted(self):
        item = HeartedItem(product_name="X", target_price=59.99)
        row = build_hearted_item_row(item)
        assert row.target_price_display == "$59.99"

    def test_archived_flag_reflected(self):
        item = HeartedItem(product_name="X", archived_at="2026-01-01T00:00:00+00:00")
        row = build_hearted_item_row(item)
        assert row.archived is True

    def test_tags_carried_through(self):
        item = HeartedItem(product_name="X", tags=["tcg", "promo"])
        row = build_hearted_item_row(item)
        assert row.tags == ["tcg", "promo"]

    def test_json_compatible(self):
        item = HeartedItem(product_name="X", tags=["a"])
        row = build_hearted_item_row(item)
        import json
        json.dumps(row.to_dict())


class TestHeartedItemRowRendering:
    def test_renders_product_name(self):
        item = HeartedItem(product_name="Vintage Print")
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert "Vintage Print" in html

    def test_manual_badge_shown_for_manual_items(self):
        item = HeartedItem(product_name="X")
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert "Manual" in html

    def test_no_manual_badge_for_atlas_linked_items(self):
        opp = make_opportunity()
        evaluation = evaluate_opportunity(opp)
        item = HeartedItem(opportunity_id=opp.opportunity_id)
        row = build_hearted_item_row(item, opportunity=opp, evaluation=evaluation)
        html = render_hearted_item_row(row)
        assert "badge--manual" not in html

    def test_unheart_button_present_and_filled(self):
        item = HeartedItem(product_name="X")
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert 'data-action="unheart"' in html
        assert 'aria-pressed="true"' in html

    def test_archive_button_present(self):
        item = HeartedItem(product_name="X")
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert 'data-action="archive-hearted"' in html
        assert "Archive" in html

    def test_archived_item_shows_unarchive(self):
        item = HeartedItem(product_name="X", archived_at="2026-01-01T00:00:00+00:00")
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert "Unarchive" in html

    def test_xss_in_product_name_escaped(self):
        item = HeartedItem(product_name="<script>alert(1)</script>")
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_data_is_manual_attribute_reflects_manual_items(self):
        item = HeartedItem(product_name="X")
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert 'data-is-manual="true"' in html

    def test_data_is_manual_attribute_false_for_atlas_linked_items(self):
        opp = make_opportunity()
        evaluation = evaluate_opportunity(opp)
        item = HeartedItem(opportunity_id=opp.opportunity_id)
        row = build_hearted_item_row(item, opportunity=opp, evaluation=evaluation)
        html = render_hearted_item_row(row)
        assert 'data-is-manual="false"' in html

    def test_xss_in_tags_escaped(self):
        item = HeartedItem(product_name="X", tags=["<img src=x onerror=alert(1)>"])
        row = build_hearted_item_row(item)
        html = render_hearted_item_row(row)
        assert "<img src=x" not in html


class TestHeartedItemsPage:
    def test_empty_state(self):
        html = render_hearted_items_page([])
        assert "No hearted items yet" in html

    def test_page_title_is_hearted_items(self):
        html = render_hearted_items_page([])
        assert "<title>Hearted Items</title>" in html

    def test_search_filter_sort_controls_present(self):
        html = render_hearted_items_page([])
        assert 'id="hi-search"' in html
        assert 'id="hi-filter-status"' in html
        assert 'id="hi-sort"' in html

    def test_add_manual_item_control_present(self):
        html = render_hearted_items_page([])
        assert 'id="hi-add-manual"' in html

    def test_nav_has_all_drops_hearted_items_and_add_item(self):
        html = render_hearted_items_page([])
        assert "All Drops" in html
        assert 'id="nav-add-item"' in html

    def test_manual_item_form_included_in_drawer(self):
        html = render_hearted_items_page([])
        assert 'id="manual-item-form"' in html
        assert 'name="product_name"' in html
        assert 'name="target_price"' in html
        assert 'name="quantity"' in html
        assert 'name="priority"' in html
        assert 'name="tags"' in html
        assert 'name="category"' in html

    def test_renders_multiple_rows(self):
        row_a = build_hearted_item_row(HeartedItem(product_name="Item A"))
        row_b = build_hearted_item_row(HeartedItem(product_name="Item B"))
        html = render_hearted_items_page([row_a, row_b])
        assert "Item A" in html
        assert "Item B" in html

    def test_deterministic_output(self):
        row = build_hearted_item_row(HeartedItem(product_name="Item"))
        html_a = render_hearted_items_page([row])
        html_b = render_hearted_items_page([row])
        assert html_a == html_b
