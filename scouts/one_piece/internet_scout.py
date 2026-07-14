import random
import time
from urllib.parse import (
    urljoin,
    urlparse,
)

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scouts.one_piece.parser import (
    parse_one_piece_item,
)
from scouts.one_piece.sources import (
    OFFICIAL_ONE_PIECE_HOSTS,
    ONE_PIECE_SOURCES,
)


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "en-US,en;q=0.9"
    ),
    "Accept-Encoding": (
        "gzip, deflate"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


PRODUCT_TERMS = [
    "booster pack",
    "booster box",
    "booster display",
    "extra booster",
    "premium booster",
    "starter deck",
    "start deck",
    "double pack",
    "tin pack",
    "devil fruits collection",
    "devil fruit collection",
    "illustration box",
    "premium card collection",
    "premium collection",
    "premium card set",
    "anniversary set",
    "promotion card",
    "promo card",
    "card collection",
    "card set",
    "tournament pack",
    "winner card",
    "playmat",
    "play mat",
    "card sleeves",
    "storage box",
    "deck case",
    "premium bandai",
]


IGNORE_TERMS = [
    "privacy",
    "cookie",
    "terms of use",
    "contact us",
    "faq",
    "rule manual",
    "play guide",
    "how to play",
    "deck recipe",
    "card list",
    "recommended decks",
    "for beginners",
    "official shop",
    "for stores",
    "store tournament",
    "championship",
    "treasure cup",
    "banned",
    "restricted",
    "errata",
]


def build_session():
    session = requests.Session()

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.5,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=[
            "GET",
        ],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=5,
        pool_maxsize=5,
    )

    session.mount(
        "https://",
        adapter,
    )

    session.mount(
        "http://",
        adapter,
    )

    session.headers.update(
        REQUEST_HEADERS
    )

    return session


def fetch_source(
    source,
    session=None,
):
    session = (
        session
        or build_session()
    )

    print(
        f"Scanning: "
        f"{source['name']}"
    )

    try:
        response = session.get(
            source["url"],
            timeout=45,
            allow_redirects=True,
        )

        if response.status_code >= 400:
            print(
                f"Source unavailable: "
                f"{source['name']} | "
                f"HTTP {response.status_code}"
            )

            return None

        print(
            f"HTTP {response.status_code} | "
            f"{len(response.text):,} "
            "characters"
        )

        return response.text

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ContentDecodingError,
    ) as error:
        print(
            f"Source temporarily blocked or "
            f"disconnected: "
            f"{source['name']} | "
            f"{type(error).__name__}"
        )

        return None

    except requests.RequestException as error:
        print(
            f"Source failed: "
            f"{source['name']} | "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return None


def extract_one_piece_items(
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
        href = clean_text(
            link.get("href")
        )

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

        title = extract_title(
            link
        )

        if not is_relevant_product(
            title
        ):
            continue

        description = extract_description(
            link
        )

        image_url = extract_image_url(
            link=link,
            base_url=source[
                "base_url"
            ],
        )

        item = parse_one_piece_item(
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


def collect_one_piece_items():
    collected = []
    session = build_session()

    try:
        for index, source in enumerate(
            ONE_PIECE_SOURCES
        ):
            html = fetch_source(
                source=source,
                session=session,
            )

            if html:
                items = extract_one_piece_items(
                    html=html,
                    source=source,
                )

                print(
                    f"Product candidates: "
                    f"{len(items)}"
                )

                collected.extend(
                    items
                )

            else:
                print(
                    f"Skipping source: "
                    f"{source['name']}"
                )

            if index < (
                len(ONE_PIECE_SOURCES)
                - 1
            ):
                delay = random.uniform(
                    1.5,
                    3.5,
                )

                time.sleep(delay)

    finally:
        session.close()

    unique_items = (
        deduplicate_one_piece_items(
            collected
        )
    )

    print("")
    print(
        f"Collected "
        f"{len(unique_items)} unique "
        "One Piece candidates"
    )

    return unique_items


def collect_official_one_piece_items():
    return collect_one_piece_items()


def deduplicate_one_piece_items(
    items,
):
    unique = {}

    for item in items:
        key = item_key(
            item
        )

        if not key:
            continue

        existing = unique.get(key)

        if existing is None:
            unique[key] = dict(item)
            continue

        unique[key] = merge_items(
            existing=existing,
            incoming=item,
        )

    return list(
        unique.values()
    )


def merge_items(
    existing,
    incoming,
):
    merged = dict(existing)

    existing_sources = (
        existing.get("sources")
        or []
    )

    incoming_sources = (
        incoming.get("sources")
        or []
    )

    if isinstance(
        existing_sources,
        str,
    ):
        existing_sources = [
            existing_sources,
        ]

    if isinstance(
        incoming_sources,
        str,
    ):
        incoming_sources = [
            incoming_sources,
        ]

    merged["sources"] = list(
        dict.fromkeys(
            existing_sources
            + incoming_sources
        )
    )

    existing_codes = (
        existing.get("set_codes")
        or []
    )

    incoming_codes = (
        incoming.get("set_codes")
        or []
    )

    if isinstance(
        existing_codes,
        str,
    ):
        existing_codes = [
            existing_codes,
        ]

    if isinstance(
        incoming_codes,
        str,
    ):
        incoming_codes = [
            incoming_codes,
        ]

    merged["set_codes"] = list(
        dict.fromkeys(
            existing_codes
            + incoming_codes
        )
    )

    if merged["set_codes"]:
        merged["primary_set_code"] = (
            merged["set_codes"][0]
        )

    for key, value in incoming.items():
        if value in (
            None,
            "",
            [],
            {},
        ):
            continue

        current = merged.get(key)

        if current in (
            None,
            "",
            [],
            {},
        ):
            merged[key] = value

        elif (
            key == "description"
            and len(str(value))
            > len(str(current))
        ):
            merged[key] = value

    return merged


def is_allowed_url(
    url,
    source,
):
    parsed = urlparse(
        url
    )

    if (
        parsed.netloc.lower()
        not in OFFICIAL_ONE_PIECE_HOSTS
    ):
        return False

    return any(
        allowed_path
        in parsed.path
        for allowed_path
        in source["allowed_paths"]
    )


def is_relevant_product(text):
    normalized = clean_text(
        text
    ).lower()

    if len(normalized) < 5:
        return False

    if any(
        term in normalized
        for term in IGNORE_TERMS
    ):
        return False

    return any(
        term in normalized
        for term in PRODUCT_TERMS
    ) or has_product_code(
        normalized
    )


def has_product_code(text):
    prefixes = [
        "op-",
        "op ",
        "eb-",
        "eb ",
        "st-",
        "st ",
        "prb-",
        "prb ",
        "dp-",
        "dp ",
        "df-",
        "df ",
        "ts-",
        "ts ",
    ]

    return any(
        prefix in text
        for prefix in prefixes
    )


def extract_title(link):
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

    return title


def extract_description(link):
    pieces = []

    aria_label = clean_text(
        link.get("aria-label")
    )

    title_attribute = clean_text(
        link.get("title")
    )

    if aria_label:
        pieces.append(
            aria_label
        )

    if title_attribute:
        pieces.append(
            title_attribute
        )

    image = link.find(
        "img"
    )

    if image:
        alt_text = clean_text(
            image.get(
                "alt",
                "",
            )
        )

        if alt_text:
            pieces.append(
                alt_text
            )

    direct_text = clean_text(
        link.get_text(
            " ",
            strip=True,
        )
    )

    if direct_text:
        pieces.append(
            direct_text
        )

    parent = link.parent

    if (
        parent is not None
        and parent.name not in {
            "body",
            "html",
        }
    ):
        parent_text = clean_text(
            parent.get_text(
                " ",
                strip=True,
            )
        )

        if (
            parent_text
            and len(parent_text) <= 1000
        ):
            pieces.append(
                parent_text
            )

    unique_pieces = list(
        dict.fromkeys(
            piece
            for piece in pieces
            if piece
        )
    )

    return clean_text(
        " ".join(
            unique_pieces
        )
    )[:1500]


def extract_image_url(
    link,
    base_url,
):
    image = link.find(
        "img"
    )

    if image is None:
        parent = link.parent

        if (
            parent is not None
            and parent.name not in {
                "body",
                "html",
            }
        ):
            image = parent.find(
                "img"
            )

    if image is None:
        return None

    value = (
        image.get("src")
        or image.get("data-src")
        or image.get(
            "data-lazy-src"
        )
    )

    if not value:
        return None

    return urljoin(
        base_url,
        str(value),
    )


def item_key(item):
    sku = clean_text(
        item.get("sku")
    ).lower()

    if sku:
        return f"sku:{sku}"

    url = clean_text(
        item.get("url")
    ).lower().rstrip("/")

    if url:
        return f"url:{url}"

    title = clean_text(
        item.get("title")
    ).lower()

    if title:
        return f"title:{title}"

    return None


def print_summary(items):
    print("")
    print("=" * 55)
    print(
        "ONE PIECE LIVE SCOUT SUMMARY"
    )
    print("=" * 55)
    print(
        f"Candidates: {len(items)}"
    )
    print("")

    for position, item in enumerate(
        items[:20],
        start=1,
    ):
        codes = (
            item.get("set_codes")
            or []
        )

        print(
            f"{position}. "
            f"{item.get('title', 'Unknown')}"
        )

        print(
            "   Codes:",
            (
                ", ".join(codes)
                if codes
                else "Unknown"
            ),
        )

        print(
            "   Source:",
            item.get(
                "source",
                "Unknown",
            ),
        )

        print(
            "   URL:",
            item.get(
                "url",
                "Unknown",
            ),
        )

        print("")


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )


def main():
    items = collect_one_piece_items()

    print_summary(items)


if __name__ == "__main__":
    main()