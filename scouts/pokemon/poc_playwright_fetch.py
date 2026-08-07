"""
Standalone retrieval feasibility test. Not part of the Atlas pipeline:
nothing in scouts/pokemon/ imports this file, and it imports nothing
from collector.py, state_tracker.py, or alert_store.py. Writes nothing
to .atlas_data or Supabase.

Usage: python scouts/pokemon/poc_playwright_fetch.py
"""

import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from scouts.pokemon.sources import POKEMON_SOURCES


SOURCE_NAME = "pokemon_center_tcg"

PARDON_INTERRUPTION_MARKERS = [
    "pardon our interruption",
]

INCAPSULA_ERROR_MARKERS = [
    "incapsula",
    "_incapsula_resource",
    "request unsuccessful",
]

VIRTUAL_QUEUE_MARKERS = [
    "queue-it",
    "queueit",
    "virtual queue",
    "you are in line",
    "estimated wait",
]

AVAILABILITY_TERMS = [
    "in stock",
    "out of stock",
    "sold out",
    "add to cart",
    "notify me",
    "coming soon",
    "preorder",
    "pre-order",
    "unavailable",
]

PRICE_PATTERN = re.compile(r"\$\s?\d+(?:,\d{3})*(?:\.\d{2})?")

MAX_SAMPLES = 5


def get_source(name):
    for source in POKEMON_SOURCES:
        if source["name"] == name:
            return source

    raise ValueError(f"No source named '{name}' in POKEMON_SOURCES")


def classify_page(title, body_text, html):
    lowered_title = (title or "").lower()
    lowered_text = (body_text or "").lower()
    lowered_html = (html or "").lower()

    if any(marker in lowered_title or marker in lowered_text for marker in PARDON_INTERRUPTION_MARKERS):
        return "PARDON_INTERRUPTION", "Matched 'Pardon Our Interruption' text."

    if any(marker in lowered_text or marker in lowered_html for marker in INCAPSULA_ERROR_MARKERS):
        return "INCAPSULA_ERROR", "Matched Incapsula error/iframe markers."

    if any(marker in lowered_text for marker in VIRTUAL_QUEUE_MARKERS):
        return "VIRTUAL_QUEUE", "Matched virtual queue language."

    return None, None


def find_candidate_products(page, source):
    # Absence of block markers isn't proof of real content, so REAL_CONTENT
    # requires positive evidence: actual product links matching the
    # source's known product path.
    anchors = page.query_selector_all("a[href]")

    seen_urls = set()
    candidates = []

    for anchor in anchors:
        href = anchor.get_attribute("href")

        if not href:
            continue

        absolute_url = urljoin(source["base_url"], href)

        if "/product/" not in absolute_url:
            continue

        if absolute_url in seen_urls:
            continue

        seen_urls.add(absolute_url)
        candidates.append((anchor, absolute_url))

    return candidates


def extract_product(anchor, url):
    title = clean_text(anchor.inner_text())

    container_text = clean_text(
        anchor.evaluate(
            "el => el.closest('li, article, div') ? "
            "el.closest('li, article, div').innerText : el.innerText"
        )
    )

    price_match = PRICE_PATTERN.search(container_text)
    price = price_match.group(0) if price_match else None

    availability = None
    lowered_container = container_text.lower()

    for term in AVAILABILITY_TERMS:
        if term in lowered_container:
            availability = term
            break

    return {
        "title": title or None,
        "url": url,
        "price": price,
        "availability": availability,
    }


def clean_text(value):
    return " ".join((value or "").split())


def run():
    source = get_source(SOURCE_NAME)

    print("=" * 64)
    print("POKÉMON CENTER PLAYWRIGHT RETRIEVAL POC")
    print("=" * 64)
    print(f"Target URL: {source['url']}")
    print("")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(source["url"], wait_until="load", timeout=30000)
        page.wait_for_timeout(4000)

        final_url = page.url
        title = page.title()
        body_text = clean_text(page.inner_text("body"))
        html = page.content()

        state, reason = classify_page(
            title=title,
            body_text=body_text,
            html=html,
        )

        candidates = []

        if state is None:
            candidates = find_candidate_products(page, source)

            if candidates:
                state = "REAL_CONTENT"
                reason = (
                    f"Found {len(candidates)} link(s) matching "
                    "the product path with no block markers present."
                )
            else:
                state = "UNKNOWN"
                reason = (
                    "No block markers matched, but no product links "
                    "were found either."
                )

        print(f"Final URL: {final_url}")
        print(f"Page title: {title}")
        print("")
        print(f"CLASSIFICATION: {state}")
        print(f"Reason: {reason}")
        print("")

        if state == "REAL_CONTENT":
            print(f"Candidate product links found: {len(candidates)}")
            print(f"Showing up to {MAX_SAMPLES} sample(s):")
            print("")

            for position, (anchor, url) in enumerate(candidates[:MAX_SAMPLES], start=1):
                product = extract_product(anchor, url)

                print(f"{position}. {product['title'] or 'Unknown title'}")
                print(f"   URL: {product['url']}")
                print(f"   Price: {product['price'] or 'Not found'}")
                print(f"   Availability: {product['availability'] or 'Not found'}")
                print("")

        else:
            print("No extraction attempted (state is not REAL_CONTENT).")
            print("")
            print("Page title snippet:")
            print(title)
            print("")
            print("Body text snippet (first 300 characters):")
            print(body_text[:300])

        browser.close()


if __name__ == "__main__":
    run()
