"""
Fetches each discovered Pokémon product's own official detail page and
enriches the item with the fields needed for real availability/restock
intelligence (price, availability, SKU, image, purchase limit, ...).

Design:
- requests-based retrieval only (see DetailPageRetriever below for why
  this is isolated behind an interface rather than hardcoded).
- Extraction is tiered: embedded structured data (JSON-LD/__NEXT_DATA__,
  reusing structured_data.py) first, then stable HTML meta tags, then
  visible page text as a last resort.
- A failed or blocked detail fetch always preserves the original,
  already-discovered item unchanged rather than discarding it.
"""

import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from acquisition.requests_retriever import RequestsRetriever
from scouts.pokemon.structured_data import (
    extract_structured_candidates,
)


# Reused from scouts/pokemon/poc_playwright_fetch.py and
# poc_safari_webdriver_fetch.py's proven block-detection markers
# (duplicated rather than imported - those files are explicitly
# standalone POCs, not pipeline dependencies).
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

CAPTCHA_MARKERS = [
    "captcha",
    "verify you are human",
    "are you a robot",
]

BLOCK_MARKERS = (
    PARDON_INTERRUPTION_MARKERS
    + INCAPSULA_ERROR_MARKERS
    + VIRTUAL_QUEUE_MARKERS
    + CAPTCHA_MARKERS
)


PRICE_PATTERN = re.compile(
    r"\$\s?\d+(?:,\d{3})*(?:\.\d{2})?"
)

PURCHASE_LIMIT_PATTERN = re.compile(
    r"limit\s+(\d+)\s+per\s+"
    r"(?:customer|order|household)"
)

AVAILABILITY_TEXT_TERMS = [
    ("add to cart", "InStock"),
    ("in stock", "InStock"),
    ("sold out", "OutOfStock"),
    ("out of stock", "OutOfStock"),
    ("notify me", "OutOfStock"),
    ("coming soon", "ComingSoon"),
    ("pre-order", "PreOrder"),
    ("preorder", "PreOrder"),
    ("unavailable", "Unavailable"),
    ("discontinued", "Unavailable"),
]

# Maps every raw availability signal this module can encounter
# (schema.org enum tail, meta tag value, or visible-text term) into
# the fixed target vocabulary. Values are chosen so that, after
# state_tracker.py's own normalization
# (.strip().lower().replace('_','').replace('-','').replace(' ','')),
# InStock/OutOfStock/PreOrder/Unavailable land exactly in the sets
# state_tracker.py already checks, while ComingSoon/Unknown correctly
# fall outside both sets (no false RESTOCK/SOLD_OUT signal).
AVAILABILITY_VOCABULARY = {
    "instock": "InStock",
    "onlineonly": "InStock",
    "instoreonly": "InStock",
    "limitedavailability": "InStock",
    "outofstock": "OutOfStock",
    "soldout": "OutOfStock",
    "soldoutonline": "OutOfStock",
    "backorder": "OutOfStock",
    "discontinued": "Unavailable",
    "unavailable": "Unavailable",
    "preorder": "PreOrder",
    "presale": "PreOrder",
    "comingsoon": "ComingSoon",
}


class DetailPageRetriever:
    """
    Interface for fetching a single detail page's raw HTML. Exists so
    a future non-requests implementation (e.g. a browser-driven
    retriever) can be substituted without changing any caller. Only a
    requests-based implementation is provided today - see the
    "requests versus browser" decision in the accompanying report.
    """

    def fetch(self, url):
        raise NotImplementedError


class RequestsDetailPageRetriever(DetailPageRetriever):

    def __init__(self, retriever=None):
        self.retriever = retriever or RequestsRetriever()

    def fetch(self, url):
        raw_content = self.retriever.fetch({
            "name": url,
            "url": url,
        })

        return raw_content.content


def classify_detail_content(html):
    if not html or not html.strip():
        return "EMPTY"

    lowered = html.lower()

    if any(
        marker in lowered
        for marker in BLOCK_MARKERS
    ):
        return "BLOCKED"

    return "OK"


def resolve_commerce_url_from_gallery_html(
    html,
    base_url,
):
    """
    Scans a pokemon.com gallery/news page's own HTML for an outbound
    link to a pokemoncenter.com product page. Only resolves when
    exactly one distinct candidate is found - a gallery listing page
    linking to many different products is genuinely ambiguous and is
    left unmapped rather than guessed at.
    """
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    for link in soup.find_all("a", href=True):
        href = link.get("href", "").strip()

        if not href:
            continue

        absolute = urljoin(
            base_url,
            href,
        ).split("#")[0]

        parsed = urlparse(absolute)

        if (
            parsed.netloc.lower()
            in {
                "www.pokemoncenter.com",
                "pokemoncenter.com",
            }
            and "/product/" in parsed.path
        ):
            candidates.append(absolute)

    unique_candidates = list(
        dict.fromkeys(candidates)
    )

    if len(unique_candidates) == 1:
        return unique_candidates[0]

    return None


def normalize_availability(raw):
    if not raw:
        return "Unknown"

    text = (
        str(raw)
        .strip()
        .split("/")[-1]
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )

    return AVAILABILITY_VOCABULARY.get(
        text,
        "Unknown",
    )


def normalize_price(raw):
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        return round(float(raw), 2)

    try:
        cleaned = (
            str(raw)
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

        if not cleaned:
            return None

        return round(float(cleaned), 2)

    except (TypeError, ValueError):
        return None


def normalize_currency(raw):
    if not raw:
        return None

    text = str(raw).strip().upper()

    if len(text) == 3 and text.isalpha():
        return text

    return None


def extract_purchase_limit(text):
    if not text:
        return None

    match = PURCHASE_LIMIT_PATTERN.search(
        text.lower()
    )

    if not match:
        return None

    try:
        return int(match.group(1))

    except (TypeError, ValueError):
        return None


def _clean_text(value):
    return " ".join(
        str(value or "").split()
    )


def _base_url_of(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _best_matching_candidate(candidates, url):
    for candidate in candidates:
        if candidate.get("url") == url:
            return candidate

    return max(
        candidates,
        key=lambda candidate: sum(
            1
            for value in candidate.values()
            if value not in (None, "", [], {})
        ),
    )


def _has_useful_fields(fields):
    return any(
        fields.get(key)
        for key in (
            "retail_price",
            "availability_raw",
            "sku",
        )
    )


def extract_via_structured_data(html, url):
    candidates = extract_structured_candidates(
        html=html,
        source={
            "base_url": _base_url_of(url),
            "url": url,
        },
    )

    if not candidates:
        return None

    candidate = _best_matching_candidate(
        candidates,
        url,
    )

    return {
        "retail_price": candidate.get(
            "retail_price"
        ),
        "currency": candidate.get(
            "currency"
        ),
        "availability_raw": candidate.get(
            "availability"
        ),
        "release_date": candidate.get(
            "release_date"
        ),
        "sku": candidate.get("sku"),
        "product_id": candidate.get(
            "product_id"
        ),
        "image_url": candidate.get(
            "image_url"
        ),
        "product_title": candidate.get(
            "title"
        ),
        "description": candidate.get(
            "description"
        ),
    }


def extract_via_meta_tags(html):
    soup = BeautifulSoup(html, "html.parser")

    def meta(name):
        tag = soup.find(
            "meta",
            attrs={"property": name},
        ) or soup.find(
            "meta",
            attrs={"name": name},
        )

        return (
            tag.get("content")
            if tag
            else None
        )

    fields = {
        "retail_price": (
            meta("product:price:amount")
            or meta("og:price:amount")
        ),
        "currency": (
            meta("product:price:currency")
            or meta("og:price:currency")
        ),
        "availability_raw": (
            meta("product:availability")
            or meta("og:availability")
        ),
        "image_url": meta("og:image"),
        "product_title": meta("og:title"),
    }

    if not _has_useful_fields(fields):
        return None

    return fields


def extract_via_visible_text(html):
    soup = BeautifulSoup(html, "html.parser")
    text = _clean_text(soup.get_text(" "))
    lowered = text.lower()

    price_match = PRICE_PATTERN.search(text)
    retail_price = (
        price_match.group(0)
        if price_match
        else None
    )

    availability_raw = None

    for term, mapped in AVAILABILITY_TEXT_TERMS:
        if term in lowered:
            availability_raw = mapped
            break

    return {
        "retail_price": retail_price,
        "availability_raw": availability_raw,
        "purchase_limit": (
            extract_purchase_limit(text)
        ),
    }


def extract_detail_fields(html, url):
    structured = extract_via_structured_data(
        html,
        url,
    )

    if structured and _has_useful_fields(
        structured
    ):
        structured["detail_source"] = (
            "structured_data"
        )

        if "purchase_limit" not in structured:
            structured["purchase_limit"] = (
                extract_purchase_limit(
                    BeautifulSoup(
                        html,
                        "html.parser",
                    ).get_text(" ")
                )
            )

        return structured

    meta_fields = extract_via_meta_tags(html)

    if meta_fields:
        meta_fields["detail_source"] = (
            "meta_tags"
        )

        meta_fields["purchase_limit"] = (
            extract_purchase_limit(
                BeautifulSoup(
                    html,
                    "html.parser",
                ).get_text(" ")
            )
        )

        return meta_fields

    text_fields = extract_via_visible_text(
        html
    )

    text_fields["detail_source"] = (
        "visible_text"
    )

    return text_fields


def _retailer_for_url(url):
    if not url:
        return None

    netloc = urlparse(url).netloc.lower()

    if "pokemoncenter.com" in netloc:
        return "Pokémon Center"

    if "pokemon.com" in netloc:
        return "Pokémon.com"

    return None


def _is_pokemon_dot_com(url):
    netloc = urlparse(url).netloc.lower()

    return netloc in {
        "www.pokemon.com",
        "pokemon.com",
    }


def merge_detail_fields(item, detail_fields, fetch_url):
    merged = dict(item)

    retail_price = normalize_price(
        detail_fields.get("retail_price")
    )

    if retail_price is not None:
        merged["retail_price"] = retail_price

    currency = normalize_currency(
        detail_fields.get("currency")
    )

    if currency:
        merged["currency"] = currency
    elif (
        retail_price is not None
        and not merged.get("currency")
    ):
        # All current sources are US commerce pages; a numeric price
        # with no explicit currency code matches the same USD-default
        # convention already used by collector.py's format_price().
        merged["currency"] = "USD"

    availability = normalize_availability(
        detail_fields.get("availability_raw")
    )

    if availability != "Unknown":
        merged["availability"] = availability
    elif not merged.get("availability"):
        merged["availability"] = "Unknown"

    merged["inventory_status"] = (
        detail_fields.get("availability_raw")
        or merged.get("inventory_status")
    )

    merged["preorder_status"] = (
        availability == "PreOrder"
    )

    release_date = detail_fields.get(
        "release_date"
    )

    if release_date:
        merged["release_date"] = release_date

    sku = detail_fields.get("sku")

    if sku and not merged.get("sku"):
        merged["sku"] = sku

    product_id = detail_fields.get(
        "product_id"
    )

    if product_id:
        merged["product_id"] = product_id

    image_url = detail_fields.get(
        "image_url"
    )

    if image_url and not merged.get(
        "image_url"
    ):
        merged["image_url"] = image_url

    # title (used everywhere for product identity/dedup - see
    # identity.py) is never overwritten by detail-page data, even
    # when the detail page's own name looks "better" - a mismatched
    # structured-data candidate could otherwise silently rewrite it
    # to an unrelated product's name. product_title is kept as its
    # own, purely informational field instead.
    product_title = detail_fields.get(
        "product_title"
    )

    merged["product_title"] = (
        product_title
        or merged.get("product_title")
        or merged.get("title")
    )

    description = detail_fields.get(
        "description"
    )

    if description and len(
        description
    ) > len(merged.get("description") or ""):
        merged["description"] = description

    purchase_limit = detail_fields.get(
        "purchase_limit"
    )

    if isinstance(purchase_limit, int):
        merged["purchase_limit"] = (
            purchase_limit
        )
    elif "purchase_limit" not in merged:
        merged["purchase_limit"] = None

    merged["retailer"] = _retailer_for_url(
        fetch_url
    ) or merged.get("retailer")

    return merged


def _stamp(item, detail_source):
    stamped = dict(item)

    stamped.setdefault(
        "discovery_url",
        item.get("url"),
    )

    stamped["detail_source"] = detail_source
    stamped["source_timestamp"] = _utc_now()

    stamped.setdefault(
        "product_title",
        item.get("title"),
    )

    stamped.setdefault("purchase_limit", None)
    stamped.setdefault(
        "preorder_status", False
    )
    stamped.setdefault(
        "inventory_status",
        item.get("availability"),
    )
    stamped.setdefault("product_id", None)
    stamped.setdefault(
        "retailer",
        _retailer_for_url(item.get("url")),
    )
    stamped.setdefault("exclusive", None)

    if not stamped.get("availability"):
        stamped["availability"] = "Unknown"

    return stamped


def _utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def _log_stage_failure(stage, url, error):
    print(
        f"[PokemonDetailCollector] {stage} "
        f"failed for {url}: "
        f"{type(error).__name__}: {error}"
    )


def collect_pokemon_product_detail(
    item,
    retriever=None,
):
    """
    Attempts to enrich `item` with data from its own official detail
    page. Always returns a dict: either the enriched version, or the
    original item (stamped with detail_source explaining why) if
    enrichment could not be completed. Never raises.
    """
    if not isinstance(item, dict):
        return item

    url = item.get("url")

    if not url:
        return _stamp(item, "no_url")

    retriever = (
        retriever
        or RequestsDetailPageRetriever()
    )

    try:
        html = retriever.fetch(url)

    except Exception as error:
        _log_stage_failure(
            stage="detail_fetch",
            url=url,
            error=error,
        )

        return _stamp(item, "fetch_failed")

    if not html:
        return _stamp(item, "fetch_failed")

    status = classify_detail_content(html)

    if status == "BLOCKED":
        print(
            "[PokemonDetailCollector] "
            f"detail_fetch blocked for {url}: "
            "bot-protection markers detected."
        )

        return _stamp(item, "blocked")

    if status == "EMPTY":
        return _stamp(
            item, "empty_response"
        )

    fetch_url = url
    mapped_from_gallery = False

    if _is_pokemon_dot_com(url):
        resolved = (
            resolve_commerce_url_from_gallery_html(
                html,
                base_url=(
                    "https://www.pokemoncenter.com"
                ),
            )
        )

        if resolved:
            try:
                commerce_html = (
                    retriever.fetch(resolved)
                )

            except Exception as error:
                _log_stage_failure(
                    stage=(
                        "detail_fetch_mapped"
                    ),
                    url=resolved,
                    error=error,
                )

                commerce_html = None

            if (
                commerce_html
                and classify_detail_content(
                    commerce_html
                )
                == "OK"
            ):
                html = commerce_html
                fetch_url = resolved
                mapped_from_gallery = True

    try:
        detail_fields = extract_detail_fields(
            html,
            fetch_url,
        )

    except Exception as error:
        _log_stage_failure(
            stage="detail_parse",
            url=fetch_url,
            error=error,
        )

        return _stamp(item, "parse_failed")

    merged = merge_detail_fields(
        item,
        detail_fields,
        fetch_url,
    )

    merged.setdefault(
        "discovery_url",
        item.get("url"),
    )

    detail_source = detail_fields.get(
        "detail_source",
        "unknown",
    )

    if mapped_from_gallery:
        merged["url"] = fetch_url
        detail_source = (
            f"{detail_source}"
            "_mapped_from_gallery"
        )

    merged["detail_source"] = detail_source
    merged["source_timestamp"] = _utc_now()

    return merged
