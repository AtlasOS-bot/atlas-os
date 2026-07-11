import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scouts.pokemon.parser import parse_pokemon_item
from scouts.pokemon.sources import POKEMON_SOURCES
from scouts.pokemon.structured_data import (
    extract_structured_candidates,
)


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

PRIORITY_TERMS = [
    "pokemon center",
    "pokémon center",
    "elite trainer box",
    "etb",
    "booster bundle",
    "booster box",
    "premium collection",
    "special collection",
    "promo card",
    "promo cards",
    "exclusive",
    "limited",
    "preorder",
    "pre-order",
    "anniversary",
    "collector",
    "collection",
    "plush",
    "figure",
    "pin",
    "trading card game",
    "tcg",
    "booster pack",
    "trainer box",
    "tin",
]

IGNORE_TERMS = [
    "privacy",
    "terms of use",
    "customer service",
    "accessibility",
    "sign in",
    "register",
    "shopping cart",
    "contact us",
    "careers",
]


def fetch_source(source):
    print(f"Scanning: {source['name']}")

    try:
        response = requests.get(
            source["url"],
            headers=REQUEST_HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        print(
            f"HTTP {response.status_code} | "
            f"{len(response.text):,} characters"
        )

        return response.text

    except requests.RequestException as error:
        print(
            f"Source failed: {source['name']} | "
            f"{type(error).__name__}: {error}"
        )

        return None


def clean_title(value):
    return " ".join(
        (value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )


def is_official_url(url):
    parsed = urlparse(url)

    return parsed.netloc.lower() in {
        "www.pokemon.com",
        "pokemon.com",
        "www.pokemoncenter.com",
        "pokemoncenter.com",
    }


def is_allowed_url(url, source):
    if not is_official_url(url):
        return False

    parsed = urlparse(url)

    return any(
        allowed_path in parsed.path
        for allowed_path in source["allowed_paths"]
    )


def is_relevant_title(title):
    normalized = title.lower()

    if len(title) < 12:
        return False

    if any(
        term in normalized
        for term in IGNORE_TERMS
    ):
        return False

    return any(
        term in normalized
        for term in PRIORITY_TERMS
    )


def extract_description(link):
    pieces = []

    image = link.find("img")

    if image:
        alt_text = clean_title(
            image.get("alt", "")
        )

        if alt_text:
            pieces.append(alt_text)

    parent = link.parent

    if parent:
        parent_text = clean_title(
            parent.get_text(
                " ",
                strip=True,
            )
        )

        if parent_text:
            pieces.append(parent_text)

    return clean_title(
        " ".join(pieces)
    )[:1000]


def extract_html_items(html, source):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    items = []
    seen_urls = set()

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = link.get(
            "href",
            "",
        ).strip()

        if not href:
            continue

        url = urljoin(
            source["base_url"],
            href,
        ).split("#")[0]

        if not is_allowed_url(
            url,
            source,
        ):
            continue

        if url in seen_urls:
            continue

        title = clean_title(
            link.get_text(
                " ",
                strip=True,
            )
        )

        image = link.find("img")

        if not title and image:
            title = clean_title(
                image.get("alt", "")
            )

        if not is_relevant_title(title):
            continue

        item = parse_pokemon_item(
            title=title,
            url=url,
            description=extract_description(
                link
            ),
        )

        item.update({
            "source": source["name"],
            "sources": [
                source["name"],
            ],
            "source_url": source["url"],
            "category": "pokemon",
            "discovery_method": "html",
        })

        items.append(item)
        seen_urls.add(url)

    return items


def structured_candidate_to_item(
    candidate,
    source,
):
    title = clean_title(
        candidate.get("title")
    )

    if not is_relevant_title(title):
        return None

    url = candidate.get("url")

    if url and not is_official_url(url):
        return None

    if not url:
        url = source["url"]

    item = parse_pokemon_item(
        title=title,
        url=url,
        description=clean_title(
            candidate.get(
                "description",
                "",
            )
        ),
    )

    item.update({
        "source": source["name"],
        "sources": [
            source["name"],
        ],
        "source_url": source["url"],
        "category": "pokemon",
        "discovery_method": (
            "structured_json"
        ),
        "retail_price": candidate.get(
            "retail_price"
        ),
        "currency": candidate.get(
            "currency"
        ),
        "availability": candidate.get(
            "availability"
        ),
        "release_date": candidate.get(
            "release_date"
        ),
        "sku": candidate.get("sku"),
        "image_url": candidate.get(
            "image_url"
        ),
        "structured_type": candidate.get(
            "structured_type"
        ),
    })

    return item


def extract_structured_items(
    html,
    source,
):
    candidates = (
        extract_structured_candidates(
            html=html,
            source=source,
        )
    )

    items = []

    for candidate in candidates:
        item = structured_candidate_to_item(
            candidate=candidate,
            source=source,
        )

        if item:
            items.append(item)

    return items


def merge_items(existing, incoming):
    combined = dict(existing)

    source_values = []

    for candidate in [
        existing.get("sources"),
        existing.get("source"),
        incoming.get("sources"),
        incoming.get("source"),
    ]:
        if isinstance(candidate, list):
            source_values.extend(candidate)

        elif candidate:
            source_values.append(candidate)

    combined["sources"] = list(
        dict.fromkeys(
            str(value)
            for value in source_values
            if value
        )
    )

    for key, value in incoming.items():
        if value in (
            None,
            "",
            [],
            {},
        ):
            continue

        current = combined.get(key)

        if current in (
            None,
            "",
            [],
            {},
        ):
            combined[key] = value

        elif (
            key == "description"
            and len(str(value))
            > len(str(current))
        ):
            combined[key] = value

    return combined


def deduplicate_items(items):
    unique = {}

    for item in items:
        key = (
            item.get("url")
            or item.get("sku")
            or item.get(
                "title",
                "",
            ).strip().lower()
        )

        if not key:
            continue

        if key not in unique:
            unique[key] = item

        else:
            unique[key] = merge_items(
                unique[key],
                item,
            )

    return list(
        unique.values()
    )


def collect_official_pokemon_items():
    collected = []

    for index, source in enumerate(
        POKEMON_SOURCES
    ):
        html = fetch_source(source)

        if html:
            html_items = extract_html_items(
                html=html,
                source=source,
            )

            structured_items = (
                extract_structured_items(
                    html=html,
                    source=source,
                )
            )

            print(
                f"HTML candidates: "
                f"{len(html_items)}"
            )

            print(
                f"Structured candidates: "
                f"{len(structured_items)}"
            )

            collected.extend(
                html_items
            )

            collected.extend(
                structured_items
            )

        if index < (
            len(POKEMON_SOURCES) - 1
        ):
            time.sleep(1)

    return deduplicate_items(
        collected
    )