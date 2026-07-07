import os
import urllib.parse
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def get_opportunities_needing_ebay_links():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={
            "ebay_sold_comps_url": "is.null",
            "select": "*",
            "limit": "50",
            "order": "created_at.desc",
        },
    )
    r.raise_for_status()
    return r.json()


def build_ebay_sold_url(query):
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.ebay.com/sch/i.html?_nkw={encoded}&LH_Sold=1&LH_Complete=1"


def update_opportunity(opp_id, query, url):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=headers(),
        params={"id": f"eq.{opp_id}"},
        json={
            "ebay_research_status": "link_created",
            "ebay_search_query": query,
            "ebay_sold_comps_url": url,
            "ebay_notes": "Open this link to manually review recent sold comps.",
        },
    )
    r.raise_for_status()


def main():
    opportunities = get_opportunities_needing_ebay_links()
    print(f"Opportunities needing eBay links: {len(opportunities)}")

    for opp in opportunities:
        brand = opp.get("brand") or ""
        item = opp.get("item_name") or ""
        query = f"{brand} {item}".strip()

        if not query:
            print(f"Skipped opportunity {opp['id']}: no query")
            continue

        url = build_ebay_sold_url(query)
        update_opportunity(opp["id"], query, url)

        print(f"Updated: {query}")
        print(url)


if __name__ == "__main__":
    main()
