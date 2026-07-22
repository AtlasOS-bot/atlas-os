"""
RetailerProductAdapter - structured retailer product data (retail
price, purchase limits, availability, SKU...) converted into a
faithful, deterministic text representation for Module 2, since
Module 2 operates on text, not structured fields.

Never invents prose: a field with no value simply doesn't produce a
line in the generated text.
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    normalize_currency_code,
    normalize_source_name,
    normalize_url,
    parse_boolean,
    parse_decimal,
    parse_quantity,
)
from collector_intelligence.ingestion_validation import (
    validate_currency,
    validate_non_empty_content,
    validate_non_negative_quantity,
    validate_price,
    validate_timestamp,
    validate_url,
)

_SIGNATURE_FIELDS = (
    "retailer", "retail_price", "sku", "purchase_limit", "availability",
    "required_spend",
)


class RetailerProductAdapter(SourceAdapter):
    name = "retailer_product"
    version = "1.0.0"
    supported_payload_types = (dict,)
    supported_source_types = ("RETAILER",)

    def can_handle(self, payload):
        if not isinstance(payload, dict):
            return False
        if not payload.get("product_name"):
            return False
        return bool(
            payload.get("retailer") or payload.get("retail_price") is not None
            or payload.get("sku") or payload.get("purchase_limit") is not None
            or payload.get("required_spend") is not None
        )

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []

        present = [f for f in _SIGNATURE_FIELDS if payload.get(f) is not None]
        confidence = min(0.55 + 0.08 * len(present), 0.95)
        return confidence, [
            f"Retailer-product-shaped payload with fields: {', '.join(present)}"
        ]

    def validate(self, payload, config):
        errors = []
        warnings = []

        errors.extend(validate_non_empty_content(
            payload.get("product_name"), payload.get("description"),
        ))

        _, price_issues = validate_price(payload.get("retail_price"), "retail_price")
        errors.extend(price_issues)

        _, spend_issues = validate_price(payload.get("required_spend"), "required_spend")
        errors.extend(spend_issues)

        _, limit_issues = validate_non_negative_quantity(
            payload.get("purchase_limit"), "purchase_limit",
        )
        errors.extend(limit_issues)

        _, currency_issues = validate_currency(payload.get("currency"), "currency", config)
        warnings.extend(currency_issues)

        _, url_issues = validate_url(payload.get("url"), "url", config)
        errors.extend(i for i in url_issues if i.severity == "ERROR")
        warnings.extend(i for i in url_issues if i.severity == "WARNING")

        _, ts_issues = validate_timestamp(payload.get("release_date"), "release_date")
        warnings.extend(ts_issues)

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        product_name = clean_text(payload.get("product_name") or "")
        description = clean_text(payload.get("description") or "")

        currency, _ = normalize_currency_code(payload.get("currency"), config.supported_currencies)
        currency = currency or "USD"

        online_available = parse_boolean(payload.get("online_available"))
        in_store_available = parse_boolean(payload.get("in_store_available"))
        membership_required = parse_boolean(payload.get("membership_required"))
        sold_individually = parse_boolean(payload.get("sold_individually"))

        lines = [f"Title:\n{product_name}"]

        if payload.get("retailer"):
            lines.append(f"Retailer:\n{clean_text(payload['retailer'])}")

        if payload.get("retail_price") is not None:
            lines.append(f"Retail price:\n{_money(parse_decimal(payload['retail_price']), currency)}")
        elif sold_individually is False:
            lines.append("Retail price:\nNot sold individually")

        if payload.get("required_spend") is not None:
            lines.append(f"Required spend:\n{_money(parse_decimal(payload['required_spend']), currency)}")

        availability_line = _availability_line(
            payload.get("availability"), online_available, in_store_available,
        )
        if availability_line:
            lines.append(f"Availability:\n{availability_line}")

        if membership_required is not None:
            lines.append(
                "Membership requirement:\n"
                + ("Membership required" if membership_required else "No membership required")
            )

        if payload.get("purchase_limit") is not None:
            quantity = parse_quantity(payload["purchase_limit"])
            lines.append(
                f"Purchase limit:\n{quantity} per qualifying order" if quantity is not None
                else f"Purchase limit:\n{payload['purchase_limit']}"
            )

        if payload.get("release_date"):
            lines.append(f"Release date:\n{payload['release_date']}")

        if description:
            lines.append(f"Description:\n{description}")

        body = "\n\n".join(lines)

        fields = {
            "title": product_name,
            "body": body,
            "source_name": normalize_source_name(payload.get("retailer")),
            "source_type": "RETAILER",
            "source_url": normalize_url(payload.get("url"), config.supported_url_schemes)[0],
            "published_at": payload.get("release_date"),
            "retailer": clean_text(payload["retailer"]) if payload.get("retailer") else None,
        }

        transformations.append(record_transformation(
            "body", payload.get("description"), body, "structured_to_text",
            "Structured retailer fields converted into a deterministic, "
            "labeled text representation for Module 2.",
        ))

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "sku": payload.get("sku") or payload.get("product_id"),
            "currency": payload.get("currency"),
            "online_available": parse_boolean(payload.get("online_available")),
            "in_store_available": parse_boolean(payload.get("in_store_available")),
            "membership_required": parse_boolean(payload.get("membership_required")),
        }

    def fingerprint(self, payload):
        return compute_fingerprint(
            canonical_url=payload.get("url"),
            source_id=payload.get("sku") or payload.get("product_id"),
            title=payload.get("product_name"),
            content=payload.get("description"),
            source_name=payload.get("retailer"),
        )


def _money(value, currency):
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}.get(currency, "")
    if symbol:
        return f"{symbol}{value:g}"
    return f"{value:g} {currency}"


def _availability_line(availability_text, online_available, in_store_available):
    if availability_text:
        return clean_text(availability_text)

    parts = []
    if online_available:
        parts.append("online")
    if in_store_available:
        parts.append("in store")

    if parts:
        return "Available " + " and ".join(parts)

    if online_available is False and in_store_available is False:
        return "Not currently available"

    return None
