"""
Standalone retrieval feasibility test using Apple's built-in safaridriver.
Not part of the Atlas pipeline: nothing imports this file, and it imports
nothing from collector.py, live_monitor.py, internet_scout.py, or the
acquisition/ package. Writes nothing to .atlas_data, Supabase, or Discord.
Does not import or modify the Playwright proof of concept.

Makes exactly one navigation attempt. No retries, no reloads, no second
Pokémon Center page.

Usage: python -m scouts.pokemon.poc_safari_webdriver_fetch
"""

import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

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

INCAPSULA_COOKIE_MARKERS = [
    "incap",
    "visid_incap",
    "nlbi",
    "reese84",
]

PRICE_PATTERN = re.compile(r"\$\s?\d+(?:,\d{3})*(?:\.\d{2})?")

MAX_SAMPLES = 5

PAGE_SETTLE_SECONDS = 4


def get_source(name):
    for source in POKEMON_SOURCES:
        if source["name"] == name:
            return source

    raise ValueError(f"No source named '{name}' in POKEMON_SOURCES")


def clean_text(value):
    return " ".join((value or "").split())


def classify_page(title, body_text, page_source):
    lowered_title = (title or "").lower()
    lowered_text = (body_text or "").lower()
    lowered_source = (page_source or "").lower()

    if any(
        marker in lowered_title or marker in lowered_text
        for marker in PARDON_INTERRUPTION_MARKERS
    ):
        return "PARDON_INTERRUPTION", "Matched 'Pardon Our Interruption' text."

    if any(
        marker in lowered_text or marker in lowered_source
        for marker in INCAPSULA_ERROR_MARKERS
    ):
        return "INCAPSULA_ERROR", "Matched Incapsula error/iframe markers."

    if any(marker in lowered_text for marker in VIRTUAL_QUEUE_MARKERS):
        return "VIRTUAL_QUEUE", "Matched virtual queue language."

    return None, None


def find_candidate_products(driver):
    # Absence of block markers isn't proof of real content, so REAL_CONTENT
    # requires positive evidence: actual product links, not just a clean page.
    anchors = driver.find_elements(
        By.CSS_SELECTOR,
        "a[href*='/product/']",
    )

    seen_urls = set()
    candidates = []

    for anchor in anchors:
        url = anchor.get_attribute("href")

        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        candidates.append((anchor, url))

    return candidates


def extract_product(driver, anchor, url):
    title = clean_text(anchor.text)

    container_text = clean_text(
        driver.execute_script(
            "var el = arguments[0]; "
            "var container = el.closest('li, article, div'); "
            "return container ? container.innerText : el.innerText;",
            anchor,
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


def report_cookie_diagnostics(cookies):
    entries = [
        (cookie.get("name", ""), cookie.get("domain", ""))
        for cookie in cookies
    ]

    incapsula_like = [
        (name, domain)
        for name, domain in entries
        if any(
            marker in name.lower()
            for marker in INCAPSULA_COOKIE_MARKERS
        )
    ]

    print(f"Cookies present: {len(entries)}")

    for name, domain in entries:
        print(f"  - {name} ({domain})")

    print("")

    if incapsula_like:
        print("Incapsula-related cookie name(s) observed:")

        for name, domain in incapsula_like:
            print(f"  - {name} ({domain})")

        print(
            "This suggests some anti-bot trust state may already have been "
            "present when this automated session connected. It does not by "
            "itself confirm that Safari reused your normal browsing session "
            "cookie-for-cookie."
        )

    else:
        print(
            "No Incapsula-related cookie names were observed. This does not "
            "confirm a fresh/isolated session either -- some sites only "
            "issue trust cookies after specific challenge flows."
        )


def run():
    source = get_source(SOURCE_NAME)

    print("=" * 64)
    print("POKÉMON CENTER SAFARI WEBDRIVER RETRIEVAL POC")
    print("=" * 64)
    print(f"Target URL: {source['url']}")
    print("")

    driver = None

    try:
        driver = webdriver.Safari()

        driver.get(source["url"])
        time.sleep(PAGE_SETTLE_SECONDS)

        final_url = driver.current_url
        title = driver.title
        body_text = clean_text(
            driver.find_element(By.TAG_NAME, "body").text
        )
        page_source = driver.page_source

        print(f"Final URL: {final_url}")
        print(f"Page title: {title}")
        print("")

        report_cookie_diagnostics(driver.get_cookies())
        print("")

        state, reason = classify_page(
            title=title,
            body_text=body_text,
            page_source=page_source,
        )

        candidates = []

        if state is None:
            candidates = find_candidate_products(driver)

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

        print(f"CLASSIFICATION: {state}")
        print(f"Reason: {reason}")
        print("")

        if state == "REAL_CONTENT":
            print(f"Candidate product links found: {len(candidates)}")
            print(f"Showing up to {MAX_SAMPLES} sample(s):")
            print("")

            for position, (anchor, url) in enumerate(
                candidates[:MAX_SAMPLES],
                start=1,
            ):
                product = extract_product(driver, anchor, url)

                print(f"{position}. {product['title'] or 'Unknown title'}")
                print(f"   URL: {product['url']}")
                print(f"   Price: {product['price'] or 'Not found'}")
                print(
                    "   Availability: "
                    f"{product['availability'] or 'Not found'}"
                )
                print("")

        else:
            print("No extraction attempted (state is not REAL_CONTENT).")
            print("")
            print("Page title snippet:")
            print(title)
            print("")
            print("Body text snippet (first 300 characters):")
            print(body_text[:300])

    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    run()
