"""
MarketplaceListingAdapter - marketplace sold/asking/auction listings.

The single most important rule here: an active asking price or an
in-progress auction bid must NEVER read as a confirmed sale. The
generated text deliberately avoids the word "sold" anywhere except in
an actually-sold listing, since Module 4's evidence classifier looks
for that word to decide sold-vs-asking - the safest way to guarantee
correctness is to never let the ambiguous case use it.
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    normalize_currency_code,
    normalize_source_name,
    normalize_unit_scope,
    normalize_url,
    parse_boolean,
    parse_quantity,
)
from collector_intelligence.ingestion_validation import (
    validate_currency,
    validate_grading_combination,
    validate_non_empty_content,
    validate_price,
    validate_sold_status_combination,
    validate_timestamp,
    validate_unit_scope,
    validate_url,
    warning as make_warning,
)

_UNIT_SCOPE_PHRASES = {
    "complete_set": "complete set",
    "pack": "single pack",
    "box": "booster box",
    "case": "sealed case",
    "lot": "card lot",
    "bundle": "bundle",
    "single_item": "single item",
}

_SIGNATURE_FIELDS = (
    "marketplace", "listing_url", "price", "sold", "listing_type", "condition",
)


class MarketplaceListingAdapter(SourceAdapter):
    name = "marketplace_listing"
    version = "1.0.0"
    supported_payload_types = (dict,)
    supported_source_types = ("MARKETPLACE",)

    def can_handle(self, payload):
        if not isinstance(payload, dict):
            return False
        has_marketplace_identity = bool(
            payload.get("marketplace") or payload.get("listing_url")
        )
        has_price = payload.get("price") is not None or payload.get("current_bid") is not None
        return has_marketplace_identity and has_price

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []

        present = [f for f in _SIGNATURE_FIELDS if payload.get(f) is not None]
        confidence = min(0.6 + 0.07 * len(present), 0.95)
        return confidence, [
            f"Marketplace-listing-shaped payload with fields: {', '.join(present)}"
        ]

    def validate(self, payload, config):
        errors = []
        warnings = []

        errors.extend(validate_non_empty_content(
            payload.get("title"), payload.get("marketplace"), field_label="title/marketplace",
        ))

        price_value = payload.get("price") if payload.get("price") is not None else payload.get("current_bid")
        _, price_issues = validate_price(price_value, "price")
        errors.extend(price_issues)

        _, currency_issues = validate_currency(payload.get("currency"), "currency", config)
        warnings.extend(currency_issues)

        _, url_issues = validate_url(payload.get("listing_url"), "listing_url", config)
        errors.extend(i for i in url_issues if i.severity == "ERROR")
        warnings.extend(i for i in url_issues if i.severity == "WARNING")

        _, ts_issues = validate_timestamp(payload.get("sold_at"), "sold_at")
        warnings.extend(ts_issues)

        _, scope_issues = validate_unit_scope(payload.get("unit_scope"), "unit_scope")
        warnings.extend(scope_issues)

        sold = parse_boolean(payload.get("sold"))
        errors.extend(validate_sold_status_combination(sold, payload.get("sold_at")))

        graded = parse_boolean(payload.get("graded"))
        errors.extend(validate_grading_combination(
            graded, payload.get("grade"), payload.get("grading_company"),
        ))

        if payload.get("retail_price") is not None:
            warnings.append(make_warning(
                "retail_price", "RETAIL_PRICE_ON_MARKETPLACE_PAYLOAD",
                "A retail_price was included on a marketplace listing "
                "payload; it is recorded as metadata only and is never "
                "used as resale/sold evidence.",
            ))

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        title = clean_text(payload.get("title") or "")
        marketplace = clean_text(payload.get("marketplace") or "")

        currency, _ = normalize_currency_code(payload.get("currency"), config.supported_currencies)
        currency = currency or "USD"

        unit_scope, _ = normalize_unit_scope(payload.get("unit_scope"))
        scope_phrase = _UNIT_SCOPE_PHRASES.get(unit_scope, "item")

        graded = parse_boolean(payload.get("graded"))
        grading_phrase = ""
        if graded is True:
            company = payload.get("grading_company")
            grade = payload.get("grade")
            details = " ".join(str(v) for v in (company, grade) if v)
            grading_phrase = f", graded{(' ' + details) if details else ''}"
        elif graded is False:
            grading_phrase = ", ungraded"

        sold = parse_boolean(payload.get("sold"))
        listing_type = (payload.get("listing_type") or "").strip().lower()
        best_offer_accepted = parse_boolean(payload.get("best_offer_accepted"))

        sentences = [f"{title} - a {scope_phrase}{grading_phrase} listed on {marketplace}."]

        # The unit-scope/grading phrase is repeated directly alongside
        # the price mention (not just in the opening line) so Module 4's
        # nearby-context classifiers reliably see it regardless of
        # sentence length.
        described_item = f"This {scope_phrase}{grading_phrase}"

        if sold is True or best_offer_accepted is True:
            money = _money(payload.get("price"), currency)
            when = f" on {payload['sold_at']}" if payload.get("sold_at") else ""
            sentences.append(f"{described_item} sold for {money}{when}.")
            price_role = "sold"
        elif listing_type == "auction" and payload.get("current_bid") is not None:
            money = _money(payload.get("current_bid"), currency)
            sentences.append(
                f"{described_item} is currently going for {money} as the "
                f"highest bid (asking/current bid, not a final sale)."
            )
            price_role = "auction_bid"
        elif payload.get("price") is not None:
            money = _money(payload.get("price"), currency)
            sentences.append(
                f"{described_item} on {marketplace} is currently selling "
                f"for {money} as an active asking price. It has not been "
                f"purchased and remains an active listing."
            )
            price_role = "asking"
        else:
            price_role = "unknown"

        status = (payload.get("status") or "").strip().lower()
        if status == "ended" and sold is not True:
            sentences.append("The listing has ended without a confirmed sale.")

        if payload.get("condition"):
            sentences.append(f"Condition: {clean_text(payload['condition'])}.")

        if payload.get("quantity") is not None and unit_scope != "single_item":
            quantity = parse_quantity(payload["quantity"])
            if quantity is not None:
                sentences.append(f"Quantity in this listing: {quantity} {scope_phrase}(s).")

        body = " ".join(sentences)

        transformations.append(record_transformation(
            "body", payload.get("title"), body, "structured_to_text",
            f"Structured marketplace listing fields converted into text; "
            f"price role classified as {price_role!r}.",
        ))

        fields = {
            "title": title,
            "body": body,
            "source_name": normalize_source_name(payload.get("marketplace")),
            "source_type": "MARKETPLACE",
            "source_url": normalize_url(payload.get("listing_url"), config.supported_url_schemes)[0],
            "published_at": payload.get("sold_at") or payload.get("listed_at"),
        }

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "listing_type": payload.get("listing_type"),
            "status": payload.get("status"),
            "sold": parse_boolean(payload.get("sold")),
            "best_offer_accepted": parse_boolean(payload.get("best_offer_accepted")),
            "condition": payload.get("condition"),
            "graded": parse_boolean(payload.get("graded")),
            "grading_company": payload.get("grading_company"),
            "grade": payload.get("grade"),
            "seller": payload.get("seller"),
            "unit_scope": normalize_unit_scope(payload.get("unit_scope"))[0],
            "currency": payload.get("currency"),
        }

    def fingerprint(self, payload):
        return compute_fingerprint(
            canonical_url=payload.get("listing_url"),
            listing_id=payload.get("listing_id"),
            title=payload.get("title"),
            content=payload.get("condition"),
            source_name=payload.get("marketplace"),
            published_at=payload.get("sold_at"),
        )


def _money(value, currency):
    if value is None:
        return "an unspecified amount"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}.get(currency, "")
    if symbol:
        return f"{symbol}{value:g}"
    return f"{value:g} {currency}"
