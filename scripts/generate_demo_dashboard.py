#!/usr/bin/env python3
"""
Atlas v21 - Module 8: DEMO dashboard generator.

Builds dashboard/demo-index.html and dashboard/demo-hearted.html from
the fabricated sample data in collector_intelligence/demo_fixtures.py -
never from Supabase. This is the "demo mode" half of the live/demo
switch:

    python scripts/generate_dashboard.py        # live mode - reads Supabase,
                                                  # writes dashboard/index.html
                                                  # and dashboard/hearted.html
    python scripts/generate_demo_dashboard.py    # demo mode - reads the local
                                                  # fixture, writes
                                                  # dashboard/demo-index.html
                                                  # and dashboard/demo-hearted.html

The two modes write to entirely different files, so demo data can
never overwrite or mix with a live-generated page, and the real
dashboard's empty-state behavior (when Supabase has no data) is
untouched by running this script. Every demo page carries a visible
"DEMO DATA" banner and every demo record's id is prefixed "demo-".

This script makes no network calls at all.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from collector_intelligence.dashboard_render import (  # noqa: E402
    render_dashboard_page, render_hearted_items_page,
)
from collector_intelligence.dashboard_view import (  # noqa: E402
    build_card_view_model, build_details_view_model, build_hearted_item_row,
)
from collector_intelligence.decision_engine import evaluate_opportunity  # noqa: E402
from collector_intelligence.demo_fixtures import (  # noqa: E402
    build_demo_hearted_items, build_demo_images, build_demo_links,
    build_demo_opportunities, build_demo_overrides,
)

DASHBOARD_DIR = os.path.join(REPO_ROOT, "dashboard")


def build_demo_pages():
    opportunities = build_demo_opportunities()
    images_by_opp = build_demo_images()
    links_by_opp = build_demo_links()
    overrides_by_opp = build_demo_overrides()
    hearted_items = build_demo_hearted_items()
    hearted_by_opp = {item.opportunity_id: item for item in hearted_items if item.opportunity_id}

    cards = []
    details_by_id = {}
    opportunities_by_id = {}
    evaluations_by_id = {}

    for opportunity in opportunities:
        evaluation = evaluate_opportunity(opportunity)
        opportunities_by_id[opportunity.opportunity_id] = opportunity
        evaluations_by_id[opportunity.opportunity_id] = evaluation

        override = overrides_by_opp.get(opportunity.opportunity_id)
        image_record = images_by_opp.get(opportunity.opportunity_id)
        user_links = links_by_opp.get(opportunity.opportunity_id)
        hearted_item = hearted_by_opp.get(opportunity.opportunity_id)

        card = build_card_view_model(
            opportunity, evaluation, override=override, image_record=image_record,
            user_links=user_links, hearted_item=hearted_item, note_count=0,
        )
        cards.append(card)
        details_by_id[opportunity.opportunity_id] = build_details_view_model(
            opportunity, evaluation, override=override,
        )

    hearted_rows = []
    for item in hearted_items:
        opportunity = opportunities_by_id.get(item.opportunity_id) if item.opportunity_id else None
        evaluation = evaluations_by_id.get(item.opportunity_id) if item.opportunity_id else None
        hearted_rows.append(build_hearted_item_row(item, opportunity=opportunity, evaluation=evaluation, note_count=0))

    index_html = render_dashboard_page(cards, details_by_id=details_by_id, demo=True)
    hearted_html = render_hearted_items_page(hearted_rows, demo=True)
    return index_html, hearted_html, len(cards), len(hearted_rows)


def main():
    index_html, hearted_html, card_count, row_count = build_demo_pages()

    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    index_path = os.path.join(DASHBOARD_DIR, "demo-index.html")
    hearted_path = os.path.join(DASHBOARD_DIR, "demo-hearted.html")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    with open(hearted_path, "w", encoding="utf-8") as f:
        f.write(hearted_html)

    print("Atlas dashboard generator - DEMO mode (no network calls, no Supabase)")
    print(f"Wrote {index_path} ({card_count} demo opportunity card(s))")
    print(f"Wrote {hearted_path} ({row_count} demo hearted item row(s))")


if __name__ == "__main__":
    raise SystemExit(main())
