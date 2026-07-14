import json
import time
from urllib.parse import (
    urljoin,
    urlparse,
)

import requests
from bs4 import BeautifulSoup

from scouts.lorcana.parser import (
    parse_lorcana_item,
)
from scouts.lorcana.sources import (
    LORCANA_SOURCES,
    OFFICIAL_LORCANA_HOSTS,
)


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/145.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": (
        "en-US,en;q=0.9"
    ),
}


PRIORITY_TERMS = [
    "disney lorcana",
    "lorcana",
    "booster",
    "starter deck",
    "starter set",
    "gift set",
    "gift box",
    "collection set",
    "collector",
    "curator",
    "trove",
    "illumineer",
    "illumineer's quest",
    "illumineers quest",
    "playmat",
    "card sleeves",
    "promo",
    "enchanted",
    "set championship",
    "challenge",
    "limited",
    "exclusive",
    "release",
    "announced",
    "preorder",
    "pre-order",
]


IGNORE_TERMS = [
    "privacy",
    "cookie",
    "terms of use",
    "accessibility",
    "contact us",
    "customer service",
    "careers",
    "newsletter",
    "sign in",
    "log in",
    "find a store",
    "how to play",
]


STRUCTURED_TYPES = {
    "Product",
    "Article",
    "NewsArticle",
    "BlogPosting",
}


def fetch_source(source):
    print(
        f"Scanning: "
        f"{source['name']}"
    )

    try:
        response = requests.get(
            source["url"],
            headers=REQUEST_HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        print(
            f"HTTP {response.status_code} | "
            f"{len(response.text):,} "
            "characters"
        )

        return response.text

    except requests.RequestException as error:
        print(
            f"Source failed: "
            f"{source['name']} | "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return None


def is_official_url(url):
    parsed = urlparse(
        url
    )

    return (
        parsed.netloc.lower()
        in OFFICIAL_LORCANA_HOSTS
    )


def is_allowed_url(
    url,
    source,
):
    if not is_official_url(url):
        return False

    parsed = urlparse(
        url
    )

    return any(
        allowed_path
        in parsed.path
        for allowed_path
        in source["allowed_paths"]
    )


def is_relevant_title(title):
    normalized = clean_text(
        title
    ).lower()

    if len(normalized) < 8:
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


def extract_html_items(
    html,
    source,
):
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
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        url = urljoin(
            source["base_url"],
            href,
        ).split("#")[0]

        if not is_allowed_url(
            url=url,
            source=source,
        ):
            continue

        if url in seen_urls:
            continue

        title = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        image = link.find(
            "img"
        )

        if not title and image:
            title = clean_text(
                image.get(
                    "alt",
                    "",
                )
            )

        if not is_relevant_title(
            title
        ):
            continue

        description = (
            extract_link_description(
                link
            )
        )

        image_url = (
            extract_image_url(
                image=image,
                base_url=source[
                    "base_url"
                ],
            )
        )

        item = parse_lorcana_item(
            title=title,
            url=url,
            description=description,
            source=source["name"],
            sources=[
                source["name"],
            ],
            source_url=source["url"],
            source_type=source[
                "source_type"
            ],
            discovery_method="html",
            image_url=image_url,
        )

        items.append(item)
        seen_urls.add(url)

    return items


def extract_structured_items(
    html,
    source,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    payloads = []

    for script in soup.find_all(
        "script",
        attrs={
            "type": (
                "application/ld+json"
            ),
        },
    ):
        payload = parse_json_script(
            script
        )

        if payload is not None:
            payloads.append(
                payload
            )

    next_data = soup.find(
        "script",
        id="__NEXT_DATA__",
    )

    if next_data:
        payload = parse_json_script(
            next_data
        )

        if payload is not None:
            payloads.append(
                payload
            )

    items = []
    seen_keys = set()

    for payload in payloads:
        for data in iter_json_objects(
            payload
        ):
            if not looks_relevant_object(
                data
            ):
                continue

            item = structured_object_to_item(
                data=data,
                source=source,
            )

            if item is None:
                continue

            key = (
                item.get("url")
                or item.get("sku")
                or item["title"].lower()
            )

            if key in seen_keys:
                continue

            seen_keys.add(key)
            items.append(item)

    return items


def structured_object_to_item(
    data,
    source,
):
    title = clean_text(
        first_value(
            data,
            [
                "name",
                "headline",
                "title",
            ],
        )
    )

    if not is_relevant_title(
        title
    ):
        return None

    url = normalize_url(
        value=first_value(
            data,
            [
                "url",
                "@id",
            ],
        ),
        base_url=source[
            "base_url"
        ],
    )

    if url and not is_official_url(
        url
    ):
        return None

    if not url:
        url = source["url"]

    description = clean_text(
        first_value(
            data,
            [
                "description",
                "abstract",
            ],
        )
    )

    offers = data.get(
        "offers"
    )

    if isinstance(
        offers,
        list,
    ):
        offers = (
            offers[0]
            if offers
            else {}
        )

    if not isinstance(
        offers,
        dict,
    ):
        offers = {}

    price = parse_price(
        offers.get("price")
        or data.get("price")
    )

    currency = (
        offers.get(
            "priceCurrency"
        )
        or data.get(
            "priceCurrency"
        )
    )

    availability = normalize_availability(
        offers.get(
            "availability"
        )
    )

    release_date = clean_text(
        first_value(
            data,
            [
                "releaseDate",
                "datePublished",
                "availabilityStarts",
            ],
        )
    ) or None

    image_url = normalize_image(
        value=data.get("image"),
        base_url=source[
            "base_url"
        ],
    )

    sku = (
        data.get("sku")
        or data.get("productID")
        or data.get("mpn")
    )

    return parse_lorcana_item(
        title=title,
        url=url,
        description=description,
        source=source["name"],
        sources=[
            source["name"],
        ],
        source_url=source["url"],
        source_type=source[
            "source_type"
        ],
        discovery_method=(
            "structured_json"
        ),
        retail_price=price,
        currency=currency,
        availability=availability,
        release_date=release_date,
        image_url=image_url,
        sku=sku,
        structured_type=data.get(
            "@type"
        ),
    )


def deduplicate_lorcana_items(
    items,
):
    unique = {}

    for item in items:
        key = item_identity_key(
            item
        )

        if not key:
            continue

        if key not in unique:
            unique[key] = dict(
                item
            )

            continue

        unique[key] = merge_items(
            existing=unique[key],
            incoming=item,
        )

    return list(
        unique.values()
    )


def item_identity_key(item):
    sku = clean_text(
        item.get("sku")
    ).lower()

    if sku:
        return f"sku:{sku}"

    url = clean_text(
        item.get("url")
    ).lower()

    if url:
        return f"url:{url}"

    title = normalize_title_key(
        item.get("title")
    )

    if title:
        return f"title:{title}"

    return None


def merge_items(
    existing,
    incoming,
):
    combined = dict(
        existing
    )

    source_values = []

    for candidate in [
        existing.get("sources"),
        existing.get("source"),
        incoming.get("sources"),
        incoming.get("source"),
    ]:
        if isinstance(
            candidate,
            list,
        ):
            source_values.extend(
                candidate
            )

        elif candidate:
            source_values.append(
                candidate
            )

    combined["sources"] = list(
        dict.fromkeys(
            str(value)
            for value in source_values
            if value
        )
    )

    for key, value in (
        incoming.items()
    ):
        if value in (
            None,
            "",
            [],
            {},
        ):
            continue

        current = combined.get(
            key
        )

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


def collect_official_lorcana_items():
    collected = []

    for index, source in enumerate(
        LORCANA_SOURCES
    ):
        html = fetch_source(
            source
        )

        if html:
            html_items = (
                extract_html_items(
                    html=html,
                    source=source,
                )
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
            len(LORCANA_SOURCES)
            - 1
        ):
            time.sleep(1)

    unique_items = (
        deduplicate_lorcana_items(
            collected
        )
    )

    print(
        f"Unique Lorcana candidates: "
        f"{len(unique_items)}"
    )

    return unique_items


def parse_json_script(script):
    text = (
        script.string
        or script.get_text()
    )

    if not text:
        return None

    try:
        return json.loads(
            text.strip()
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return None


def iter_json_objects(value):
    if isinstance(
        value,
        dict,
    ):
        yield value

        for nested_value in (
            value.values()
        ):
            yield from iter_json_objects(
                nested_value
            )

    elif isinstance(
        value,
        list,
    ):
        for nested_value in value:
            yield from iter_json_objects(
                nested_value
            )


def looks_relevant_object(data):
    if not isinstance(
        data,
        dict,
    ):
        return False

    object_type = data.get(
        "@type"
    )

    if isinstance(
        object_type,
        list,
    ):
        object_types = set(
            object_type
        )

    elif object_type:
        object_types = {
            object_type,
        }

    else:
        object_types = set()

    recognized_type = bool(
        object_types
        & STRUCTURED_TYPES
    )

    title = clean_text(
        first_value(
            data,
            [
                "name",
                "headline",
                "title",
            ],
        )
    )

    return (
        recognized_type
        and is_relevant_title(title)
    )


def first_value(
    data,
    keys,
):
    for key in keys:
        value = data.get(
            key
        )

        if value not in (
            None,
            "",
            [],
            {},
        ):
            return value

    return None


def extract_link_description(link):
    parent = link.parent

    if parent is None:
        return ""

    return clean_text(
        parent.get_text(
            " ",
            strip=True,
        )
    )[:1200]


def extract_image_url(
    image,
    base_url,
):
    if image is None:
        return None

    value = (
        image.get("src")
        or image.get("data-src")
        or image.get("data-lazy-src")
    )

    if not value:
        return None

    return urljoin(
        base_url,
        str(value),
    )


def normalize_url(
    value,
    base_url,
):
    if isinstance(
        value,
        dict,
    ):
        value = (
            value.get("@id")
            or value.get("url")
        )

    if not isinstance(
        value,
        str,
    ):
        return None

    return urljoin(
        base_url,
        value,
    ).split("#")[0]


def normalize_image(
    value,
    base_url,
):
    if isinstance(
        value,
        list,
    ):
        value = (
            value[0]
            if value
            else None
        )

    if isinstance(
        value,
        dict,
    ):
        value = (
            value.get("url")
            or value.get(
                "contentUrl"
            )
        )

    if not isinstance(
        value,
        str,
    ):
        return None

    return urljoin(
        base_url,
        value,
    )


def normalize_availability(value):
    if not value:
        return None

    return (
        str(value)
        .split("/")[-1]
        .strip()
    )


def parse_price(value):
    if value is None:
        return None

    try:
        return float(
            str(value)
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def normalize_title_key(value):
    return " ".join(
        clean_text(value)
        .lower()
        .replace("disney lorcana", "")
        .replace("trading card game", "")
        .split()
    )


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )