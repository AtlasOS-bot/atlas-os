import json
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PRODUCT_TYPES = {
    "Product",
    "IndividualProduct",
    "Article",
    "NewsArticle",
}

TITLE_KEYS = [
    "name",
    "headline",
    "title",
]

URL_KEYS = [
    "url",
    "@id",
]

DESCRIPTION_KEYS = [
    "description",
    "abstract",
]

DATE_KEYS = [
    "releaseDate",
    "datePublished",
    "dateCreated",
    "availabilityStarts",
]

PRICE_KEYS = [
    "price",
    "lowPrice",
    "highPrice",
]


def clean_text(value):
    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )


def first_value(data, keys):
    for key in keys:
        value = data.get(key)

        if value not in (None, "", [], {}):
            return value

    return None


def normalize_url(value, base_url):
    if isinstance(value, dict):
        value = (
            value.get("@id")
            or value.get("url")
        )

    if not isinstance(value, str):
        return None

    url = urljoin(
        base_url,
        value,
    )

    return url.split("#")[0]


def normalize_image(value, base_url):
    if isinstance(value, list):
        value = value[0] if value else None

    if isinstance(value, dict):
        value = (
            value.get("url")
            or value.get("contentUrl")
        )

    if not isinstance(value, str):
        return None

    return urljoin(
        base_url,
        value,
    )


def extract_price(data):
    offers = data.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else None

    price_source = (
        offers
        if isinstance(offers, dict)
        else data
    )

    for key in PRICE_KEYS:
        value = price_source.get(key)

        if value is None:
            continue

        try:
            return float(
                str(value)
                .replace("$", "")
                .replace(",", "")
                .strip()
            )
        except ValueError:
            continue

    return None


def extract_currency(data):
    offers = data.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else None

    if isinstance(offers, dict):
        return (
            offers.get("priceCurrency")
            or data.get("priceCurrency")
        )

    return data.get("priceCurrency")


def extract_availability(data):
    offers = data.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else None

    if not isinstance(offers, dict):
        return None

    availability = offers.get("availability")

    if not availability:
        return None

    return str(availability).split("/")[-1]


def iter_objects(value):
    if isinstance(value, dict):
        yield value

        for nested_value in value.values():
            yield from iter_objects(
                nested_value
            )

    elif isinstance(value, list):
        for nested_value in value:
            yield from iter_objects(
                nested_value
            )


def looks_like_product(data):
    object_type = data.get("@type")

    if isinstance(object_type, list):
        object_types = set(object_type)
    elif object_type:
        object_types = {object_type}
    else:
        object_types = set()

    if object_types.intersection(
        PRODUCT_TYPES
    ):
        return True

    has_title = any(
        data.get(key)
        for key in TITLE_KEYS
    )

    has_product_detail = any([
        data.get("offers"),
        data.get("sku"),
        data.get("productID"),
        data.get("releaseDate"),
    ])

    return bool(
        has_title
        and has_product_detail
    )


def object_to_candidate(data, source):
    title = clean_text(
        first_value(
            data,
            TITLE_KEYS,
        )
    )

    if not title:
        return None

    url = normalize_url(
        first_value(
            data,
            URL_KEYS,
        ),
        source["base_url"],
    )

    description = clean_text(
        first_value(
            data,
            DESCRIPTION_KEYS,
        )
    )

    release_date = clean_text(
        first_value(
            data,
            DATE_KEYS,
        )
    ) or None

    return {
        "title": title,
        "url": url,
        "description": description,
        "retail_price": extract_price(
            data
        ),
        "currency": extract_currency(
            data
        ),
        "availability": extract_availability(
            data
        ),
        "release_date": release_date,
        "sku": (
            data.get("sku")
            or data.get("productID")
            or data.get("mpn")
        ),
        "product_id": (
            data.get("productID")
            or data.get("mpn")
        ),
        "image_url": normalize_image(
            data.get("image"),
            source["base_url"],
        ),
        "structured_type": data.get("@type"),
    }


def parse_json_script(script):
    text = script.string or script.get_text()

    if not text:
        return []

    text = text.strip()

    if not text:
        return []

    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        return []


def extract_structured_candidates(
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
            "type": "application/ld+json",
        },
    ):
        payloads.extend(
            parse_json_script(script)
        )

    next_data = soup.find(
        "script",
        id="__NEXT_DATA__",
    )

    if next_data:
        payloads.extend(
            parse_json_script(next_data)
        )

    candidates = []
    seen = set()

    for payload in payloads:
        for data in iter_objects(payload):
            if not looks_like_product(data):
                continue

            candidate = object_to_candidate(
                data=data,
                source=source,
            )

            if not candidate:
                continue

            key = (
                candidate.get("url")
                or candidate.get("sku")
                or candidate["title"].lower()
            )

            if key in seen:
                continue

            seen.add(key)
            candidates.append(candidate)

    return candidates