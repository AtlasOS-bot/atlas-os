#!/usr/bin/env python3
"""
Atlas v21 - Module 8 integration layer.

Generates dashboard/index.html (Opportunities) and dashboard/hearted.html
(Hearted Items) from live Supabase data. All classification, override
resolution, image priority, and card formatting happens here in Python
via collector_intelligence.dashboard_view/dashboard_render - nothing in
dashboard/app.js re-derives any of it.

This is a MANUAL entrypoint. Nothing in this repository runs it
automatically, matching every other migration/build step here (see
db/README.md). Run it yourself from the repo root:

    python scripts/generate_dashboard.py

Configuration (env vars):
    SUPABASE_URL          - defaults to the same project URL already
                             committed in dashboard/app.js (not a
                             secret - just a project identifier).
    SUPABASE_SERVICE_KEY  - REQUIRED, no default. As of the password-
                             protected deployment, anon has no access
                             to collector_opportunities or any dashboard
                             table (db/migrations/0003 and 0005) - this
                             script now reads with the same service-role
                             credential the GitHub Actions pipeline and
                             the FastAPI app use, matching every other
                             trusted server-side script in this repo
                             (atlas/*.py). Set it in your own shell
                             (never commit it) before running this.

Read-only: this script only ever issues GET requests, against
collector_opportunities and the 6 Module 8 tables (see
db/migrations/0001 and 0002). It never writes.

Whether these tables exist in your live project is NOT something this
repository can verify - see db/README.md. This script does not assume
success: it reports exactly what it could and could not read from each
table, and treats anything unreadable as absent data rather than
inventing a fallback value for it.
"""

import os
import sys

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from collector_intelligence.dashboard_models import (  # noqa: E402
    HeartedItem, OpportunityImage, OpportunityUserOverride, UserExternalLink,
)
from collector_intelligence.dashboard_render import (  # noqa: E402
    render_dashboard_page, render_hearted_items_page,
)
from collector_intelligence.dashboard_view import (  # noqa: E402
    build_card_view_model, build_details_view_model, build_hearted_item_row,
)
from collector_intelligence.decision_engine import evaluate_opportunity  # noqa: E402
from collector_intelligence.models import CollectorOpportunity  # noqa: E402


# Not a secret - the project URL is already public in dashboard/app.js.
DEFAULT_SUPABASE_URL = "https://fdvgndlwajhjyxttfiht.supabase.co"

SUPABASE_URL = os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL)
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_SERVICE_KEY:
    raise SystemExit(
        "SUPABASE_SERVICE_KEY is required (anon no longer has access to "
        "any of these tables - see db/migrations/0003 and 0005). Set it "
        "in your shell before running this script; never commit it."
    )

DASHBOARD_DIR = os.path.join(REPO_ROOT, "dashboard")

TABLES_TO_READ = [
    "collector_opportunities",
    "opportunity_images",
    "user_external_links",
    "opportunity_notes",
    "opportunity_user_overrides",
    "hearted_items",
    "hearted_item_notes",
]


class TableFetchResult:
    def __init__(self, table, rows=None, error=None):
        self.table = table
        self.rows = rows if rows is not None else []
        self.error = error

    @property
    def ok(self):
        return self.error is None


def fetch_table(table, timeout=15):
    """GET-only against Supabase's REST API. Never raises - a missing
    table, a network failure, or an RLS-blocked read all come back as
    a TableFetchResult with `.error` set, so one bad table can't take
    down the rest of the generation run, and callers never have to
    guess whether a table is reachable."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        return TableFetchResult(table, error=f"network error: {exc}")

    if response.status_code != 200:
        return TableFetchResult(table, error=f"HTTP {response.status_code}: {response.text[:300]!r}")

    try:
        payload = response.json()
    except ValueError:
        return TableFetchResult(table, error="response body was not valid JSON")

    if not isinstance(payload, list):
        return TableFetchResult(table, error=f"expected a JSON array, got {type(payload).__name__}: {payload!r}"[:300])

    return TableFetchResult(table, rows=payload)


def fetch_all_tables():
    results = {}
    print(f"Atlas dashboard generator - reading from {SUPABASE_URL}")
    for table in TABLES_TO_READ:
        result = fetch_table(table)
        results[table] = result
        if result.ok:
            print(f"  [ok]   {table}: {len(result.rows)} row(s)")
        else:
            print(f"  [FAIL] {table}: {result.error}")
    print()
    return results


def build_pages(results):
    opportunities_result = results["collector_opportunities"]
    opportunity_rows = opportunities_result.rows if opportunities_result.ok else []

    images_by_opp = {}
    if results["opportunity_images"].ok:
        for row in results["opportunity_images"].rows:
            images_by_opp[row.get("opportunity_id")] = OpportunityImage.from_dict(row)

    links_by_owner = {}
    if results["user_external_links"].ok:
        for row in results["user_external_links"].rows:
            key = (row.get("owner_type"), row.get("owner_id"))
            links_by_owner.setdefault(key, []).append(UserExternalLink.from_dict(row))

    notes_count_by_opp = {}
    if results["opportunity_notes"].ok:
        for row in results["opportunity_notes"].rows:
            opp_id = row.get("opportunity_id")
            notes_count_by_opp[opp_id] = notes_count_by_opp.get(opp_id, 0) + 1

    hearted_notes_count_by_item = {}
    if results["hearted_item_notes"].ok:
        for row in results["hearted_item_notes"].rows:
            item_id = row.get("hearted_item_id")
            hearted_notes_count_by_item[item_id] = hearted_notes_count_by_item.get(item_id, 0) + 1

    overrides_by_opp = {}
    if results["opportunity_user_overrides"].ok:
        for row in results["opportunity_user_overrides"].rows:
            overrides_by_opp[row.get("opportunity_id")] = OpportunityUserOverride.from_dict(row)

    hearted_items = []
    if results["hearted_items"].ok:
        hearted_items = [HeartedItem.from_dict(row) for row in results["hearted_items"].rows]
    hearted_by_opp = {item.opportunity_id: item for item in hearted_items if item.opportunity_id}

    cards = []
    details_by_id = {}
    opportunities_by_id = {}
    evaluations_by_id = {}

    for row in opportunity_rows:
        opportunity = CollectorOpportunity.from_dict(row)
        evaluation = evaluate_opportunity(opportunity)
        opportunities_by_id[opportunity.opportunity_id] = opportunity
        evaluations_by_id[opportunity.opportunity_id] = evaluation

        override = overrides_by_opp.get(opportunity.opportunity_id)
        image_record = images_by_opp.get(opportunity.opportunity_id)
        user_links = links_by_owner.get(("opportunity", opportunity.opportunity_id))
        hearted_item = hearted_by_opp.get(opportunity.opportunity_id)
        note_count = notes_count_by_opp.get(opportunity.opportunity_id, 0)

        card = build_card_view_model(
            opportunity, evaluation, override=override, image_record=image_record,
            user_links=user_links, hearted_item=hearted_item, note_count=note_count,
        )
        cards.append(card)
        details_by_id[opportunity.opportunity_id] = build_details_view_model(
            opportunity, evaluation, override=override,
        )

    hearted_rows = []
    for item in hearted_items:
        opportunity = opportunities_by_id.get(item.opportunity_id) if item.opportunity_id else None
        evaluation = evaluations_by_id.get(item.opportunity_id) if item.opportunity_id else None
        note_count = hearted_notes_count_by_item.get(item.id, 0)
        hearted_rows.append(build_hearted_item_row(item, opportunity=opportunity, evaluation=evaluation, note_count=note_count))

    index_html = render_dashboard_page(cards, details_by_id=details_by_id)
    hearted_html = render_hearted_items_page(hearted_rows)

    return index_html, hearted_html, len(cards), len(hearted_rows)


def write_pages(index_html, hearted_html):
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    index_path = os.path.join(DASHBOARD_DIR, "index.html")
    hearted_path = os.path.join(DASHBOARD_DIR, "hearted.html")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    with open(hearted_path, "w", encoding="utf-8") as f:
        f.write(hearted_html)

    return index_path, hearted_path


def main():
    results = fetch_all_tables()
    index_html, hearted_html, card_count, row_count = build_pages(results)
    index_path, hearted_path = write_pages(index_html, hearted_html)

    print(f"Wrote {index_path} ({card_count} opportunity card(s))")
    print(f"Wrote {hearted_path} ({row_count} hearted item row(s))")

    failures = [table for table, result in results.items() if not result.ok]
    if failures:
        print()
        print("WARNING - could not read from: " + ", ".join(failures))
        print(
            "The pages above were generated using only the tables that "
            "were reachable; anything from an unreadable table was "
            "treated as absent, never invented. This usually means the "
            "table doesn't exist yet in this Supabase project, RLS is "
            "blocking the anon key, or the project is unreachable - see "
            "db/README.md for the migrations that create these tables "
            "and db/migrations/0003_enable_dashboard_rls_policies.sql "
            "for the RLS policies they need."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
