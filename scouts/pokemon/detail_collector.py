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


# Loosely based on scouts/pokemon/poc_playwright_fetch.py and
# poc_safari_webdriver_fetch.py's block-detection markers (duplicated
# rather than imported - those files are explicitly standalone POCs,
# not pipeline dependencies), but narrowed after a real production
# false-positive: pokemon.com legitimately loads an async
# /_Incapsula_Resource bot-fingerprinting script and a reCAPTCHA
# Enterprise script on every normal page as always-on risk scoring,
# not only on actual block pages. Bare "incapsula" and "captcha"
# substrings therefore misclassify real content as blocked. Markers
# here are restricted to phrases only ever observed on the actual
# interruption/challenge page itself (see
# tests/test_pokemon_detail_collector.py for the exact fixtures that
# proved this).
PARDON_INTERRUPTION_MARKERS = [
    "pardon our interruption",
]

INCAPSULA_ERROR_MARKERS = [
    "request unsuccessful. incapsula",
    "incapsula incident id",
]

VIRTUAL_QUEUE_MARKERS = [
    "queue-it",
    "queueit",
    "virtual queue",
    "you are in line",
    "estimated wait",
]

CAPTCHA_MARKERS = [
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


def _matched_block_marker(html):
    lowered = html.lower()

    for marker in BLOCK_MARKERS:
        if marker in lowered:
            return marker

    return None


def classify_detail_content(html):
    if not html or not html.strip():
        return "EMPTY"

    if _matched_block_marker(html):
        return "BLOCKED"

    return "OK"


def find_commerce_links(html, base_url):
    """
    Scans a page's own HTML for outbound links to pokemoncenter.com
    product pages. Returns every distinct match (order preserved) -
    callers decide what "ambiguous" means for their purpose.
    """
    if not html:
        return []

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

    return list(dict.fromkeys(candidates))


def resolve_commerce_url_from_gallery_html(
    html,
    base_url,
):
    """
    Only resolves when exactly one distinct candidate is found - a
    gallery listing page linking to many different products is
    genuinely ambiguous and is left unmapped rather than guessed at.
    """
    unique_candidates = find_commerce_links(
        html,
        base_url,
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
            "image_url",
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


def extract_via_meta_tags(html, base_url=None):
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

    image_url = meta("og:image")

    if image_url and base_url:
        image_url = urljoin(
            base_url,
            image_url,
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
        "image_url": image_url,
        "product_title": meta("og:title"),
    }

    if not _has_useful_fields(fields):
        return None

    return fields


MONTH_NAME_DATE_PATTERN = re.compile(
    r"(?:launch|release date|releases?|"
    r"available)\s*:?\s*"
    r"(January|February|March|April|May|"
    r"June|July|August|September|October|"
    r"November|December)\s+(\d{1,2}),?\s+"
    r"(\d{4})",
    re.IGNORECASE,
)


def extract_release_date_from_text(text):
    if not text:
        return None

    match = MONTH_NAME_DATE_PATTERN.search(
        text
    )

    if not match:
        return None

    month_name, day, year = match.groups()

    try:
        parsed = datetime.strptime(
            f"{month_name} {day} {year}",
            "%B %d %Y",
        )

        return parsed.date().isoformat()

    except ValueError:
        return None


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
        "release_date": (
            extract_release_date_from_text(
                text
            )
        ),
        "purchase_limit": (
            extract_purchase_limit(text)
        ),
    }


# The full set of fields any extraction tier may contribute.
# Precedence when combining tiers: structured data > meta tags >
# visible text - a weaker tier only ever fills a field a stronger
# tier left missing, never overwrites one.
DETAIL_FIELD_KEYS = [
    "retail_price",
    "currency",
    "availability_raw",
    "release_date",
    "sku",
    "product_id",
    "image_url",
    "product_title",
    "description",
    "purchase_limit",
]


def _is_missing(value):
    return value in (None, "", [], {})


def _merge_tier_fields(
    accumulated,
    tier_fields,
    tier_name,
    contributing_sources,
):
    contributed = False

    for key in DETAIL_FIELD_KEYS:
        if key not in tier_fields:
            continue

        value = tier_fields.get(key)

        if _is_missing(value):
            continue

        if _is_missing(
            accumulated.get(key)
        ):
            accumulated[key] = value
            contributed = True

    if contributed:
        contributing_sources.append(
            tier_name
        )

    return contributed


def extract_detail_fields(html, url):
    """
    Runs all three extraction tiers unconditionally and combines
    them - a weaker tier only fills fields a stronger tier left
    missing, it never overwrites an already-populated value. Finding
    e.g. only image_url via meta tags does not prevent the visible-
    text tier from being searched for retail price, availability,
    release date, SKU, or purchase limit.

    Returns every key in DETAIL_FIELD_KEYS (None if never found),
    plus:
    - detail_source: the single strongest tier that contributed at
      least one field (backward-compatible scalar, used for the
      "_mapped_from_gallery" suffix and existing callers/tests).
    - detail_sources: every tier that actually contributed at least
      one field, strongest first - a small provenance list, not a
      second schema.
    """
    accumulated = {
        key: None
        for key in DETAIL_FIELD_KEYS
    }
    contributing_sources = []

    structured = extract_via_structured_data(
        html,
        url,
    )

    if structured:
        _merge_tier_fields(
            accumulated,
            structured,
            "structured_data",
            contributing_sources,
        )

    meta_fields = extract_via_meta_tags(
        html,
        base_url=_base_url_of(url),
    )

    if meta_fields:
        _merge_tier_fields(
            accumulated,
            meta_fields,
            "meta_tags",
            contributing_sources,
        )

    text_fields = extract_via_visible_text(
        html
    )

    _merge_tier_fields(
        accumulated,
        text_fields,
        "visible_text",
        contributing_sources,
    )

    accumulated["detail_sources"] = (
        contributing_sources
    )

    accumulated["detail_source"] = (
        contributing_sources[0]
        if contributing_sources
        else "none"
    )

    return accumulated


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
    stamped.setdefault("detail_sources", [])
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


# High-value fields checked to report, per product, which of the
# fields this whole feature exists to populate actually ended up
# populated. Only field names/booleans are logged - never field
# values, cookies, credentials, or headers.
HIGH_VALUE_FIELDS = [
    "retail_price",
    "availability",
    "sku",
    "image_url",
    "release_date",
    "purchase_limit",
]


def _populated_high_value_fields(item):
    populated = []

    for field in HIGH_VALUE_FIELDS:
        value = item.get(field)

        if value not in (None, "", "Unknown"):
            populated.append(field)

    return populated


def _new_diagnostic(url):
    return {
        "discovery_url": url,
        "fetch_status": None,
        "response_length": None,
        "blocked": False,
        "commerce_links_found": None,
        "mapped_url": None,
        "extraction_source": None,
        "fields_populated": [],
        "reason": None,
    }


def _print_diagnostic(diagnostic):
    populated = (
        ",".join(
            diagnostic["fields_populated"]
        )
        or "none"
    )

    print(
        "[PokemonDetailCollector] diagnostic "
        f"url={diagnostic['discovery_url']} "
        f"fetch={diagnostic['fetch_status']} "
        f"len={diagnostic['response_length']} "
        f"blocked={diagnostic['blocked']} "
        "commerce_links="
        f"{diagnostic['commerce_links_found']} "
        f"mapped_url={diagnostic['mapped_url']} "
        f"source={diagnostic['extraction_source']} "
        f"populated=[{populated}] "
        f"reason={diagnostic['reason']}"
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

    Prints exactly one concise diagnostic line per call (see
    _print_diagnostic) so a scheduled run's logs make it possible to
    tell "ran but the page had nothing useful" apart from "never
    actually attempted anything" - only URLs, counts, and field
    names are logged, never cookies, credentials, headers, or field
    values.
    """
    if not isinstance(item, dict):
        return item

    url = item.get("url")

    diagnostic = _new_diagnostic(url)

    if not url:
        diagnostic["fetch_status"] = "skipped"
        diagnostic["reason"] = (
            "item_has_no_url"
        )
        _print_diagnostic(diagnostic)

        return _stamp(item, "no_url")

    retriever = (
        retriever
        or RequestsDetailPageRetriever()
    )

    try:
        html = retriever.fetch(url)

    except Exception as error:
        diagnostic["fetch_status"] = "error"
        diagnostic["reason"] = (
            f"{type(error).__name__}"
        )
        _print_diagnostic(diagnostic)

        _log_stage_failure(
            stage="detail_fetch",
            url=url,
            error=error,
        )

        return _stamp(item, "fetch_failed")

    diagnostic["response_length"] = (
        len(html) if html else 0
    )

    if not html or not html.strip():
        diagnostic["fetch_status"] = "empty"
        diagnostic["reason"] = (
            "no_content_returned"
        )
        _print_diagnostic(diagnostic)

        return _stamp(item, "fetch_failed")

    diagnostic["fetch_status"] = "ok"

    matched_marker = _matched_block_marker(
        html
    )

    if matched_marker:
        diagnostic["blocked"] = True
        diagnostic["reason"] = (
            f"block_marker_matched:"
            f"{matched_marker}"
        )
        _print_diagnostic(diagnostic)

        return _stamp(item, "blocked")

    fetch_url = url
    mapped_from_gallery = False

    if _is_pokemon_dot_com(url):
        commerce_links = find_commerce_links(
            html,
            base_url=(
                "https://www.pokemoncenter.com"
            ),
        )

        diagnostic[
            "commerce_links_found"
        ] = len(commerce_links)

        resolved = (
            commerce_links[0]
            if len(commerce_links) == 1
            else None
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
                diagnostic[
                    "mapped_url"
                ] = resolved

    try:
        detail_fields = extract_detail_fields(
            html,
            fetch_url,
        )

    except Exception as error:
        diagnostic["reason"] = (
            f"parse_error:"
            f"{type(error).__name__}"
        )
        _print_diagnostic(diagnostic)

        _log_stage_failure(
            stage="detail_parse",
            url=fetch_url,
            error=error,
        )

        return _stamp(item, "parse_failed")

    detail_sources = detail_fields.get(
        "detail_sources",
        [],
    )

    diagnostic["extraction_source"] = (
        "+".join(detail_sources)
        if detail_sources
        else "none"
    )

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
    merged["detail_sources"] = detail_sources
    merged["source_timestamp"] = _utc_now()

    diagnostic["fields_populated"] = (
        _populated_high_value_fields(merged)
    )

    diagnostic["reason"] = (
        "enriched"
        if diagnostic["fields_populated"]
        else (
            "page_fetched_but_no_price_"
            "availability_sku_image_"
            "release_date_or_limit_found"
        )
    )

    _print_diagnostic(diagnostic)

    return merged
