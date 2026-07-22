"""
StructuredCollectorReportAdapter - the trusted internal schema future
scouts will emit directly. Strict and strongly validated: this is the
one adapter where the payload shape is fully within Atlas's control,
so there's no excuse for a missing product identity.

Expected shape (all sections except product_identity are optional):

{
    "schema_version": "1.0",
    "product_identity": {"product_name": ..., "brand": ..., ...},
    "source_details": {"source_name": ..., "source_type": ..., ...},
    "release_details": {"release_date": ..., "status": ..., ...},
    "retail_details": {"retail_price": ..., "required_spend": ..., ...},
    "market_observations": [{"price": ..., "kind": "sold"|"asking", ...}],
    "collector_characteristics": {"exclusive_promo": True, ...},
    "acquisition_details": {"membership_required": ..., ...},
    "status": "confirmed" | "rumored" | ...,
    "confidence": 0-100,   # informational only - not authoritative scoring
    "evidence_excerpts": ["...", "..."],
}
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    normalize_currency_code,
    normalize_source_name,
    normalize_source_type,
    normalize_url,
)
from collector_intelligence.ingestion_validation import (
    validate_currency,
    validate_price,
    validate_url,
    error as make_error,
)

_MONEY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}


class StructuredCollectorReportAdapter(SourceAdapter):
    name = "structured_collector_report"
    version = "1.0.0"
    supported_payload_types = (dict,)
    supported_source_types = ()

    def can_handle(self, payload):
        if not isinstance(payload, dict):
            return False
        return "schema_version" in payload and isinstance(
            payload.get("product_identity"), dict
        )

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []
        return 0.97, [
            "Payload carries the internal structured-report schema marker "
            "(schema_version + product_identity) - unambiguous by design"
        ]

    def validate(self, payload, config):
        errors = []
        warnings = []

        identity = payload.get("product_identity")
        if not isinstance(identity, dict) or not identity.get("product_name"):
            errors.append(make_error(
                "product_identity.product_name", "MISSING_REQUIRED_FIELD",
                "A structured collector report must include "
                "product_identity.product_name.",
            ))
            return errors, warnings

        if not identity.get("brand") and not identity.get("franchise"):
            errors.append(make_error(
                "product_identity.brand", "MISSING_REQUIRED_FIELD",
                "A structured collector report must include at least one "
                "of product_identity.brand or product_identity.franchise.",
            ))

        retail = payload.get("retail_details") or {}
        for field_name in ("retail_price", "required_spend"):
            _, issues = validate_price(retail.get(field_name), field_name)
            errors.extend(issues)

        _, currency_issues = validate_currency(
            retail.get("currency"), "retail_details.currency", config,
        )
        warnings.extend(currency_issues)

        source_details = payload.get("source_details") or {}
        _, url_issues = validate_url(
            source_details.get("source_url"), "source_details.source_url", config,
        )
        errors.extend(i for i in url_issues if i.severity == "ERROR")
        warnings.extend(i for i in url_issues if i.severity == "WARNING")

        confidence = payload.get("confidence")
        if confidence is not None and not (0 <= confidence <= 100):
            errors.append(make_error(
                "confidence", "OUT_OF_RANGE",
                f"confidence must be between 0 and 100, got {confidence}.",
            ))

        for i, observation in enumerate(payload.get("market_observations") or []):
            _, issues = validate_price(observation.get("price"), f"market_observations[{i}].price")
            errors.extend(issues)

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        identity = payload.get("product_identity") or {}
        source_details = payload.get("source_details") or {}
        release_details = payload.get("release_details") or {}
        retail_details = payload.get("retail_details") or {}
        collector_characteristics = payload.get("collector_characteristics") or {}
        acquisition_details = payload.get("acquisition_details") or {}
        market_observations = payload.get("market_observations") or []
        evidence_excerpts = payload.get("evidence_excerpts") or []

        product_name = clean_text(identity.get("product_name") or "")
        currency, _ = normalize_currency_code(
            retail_details.get("currency"), config.supported_currencies,
        )
        currency = currency or "USD"

        lines = [f"Product:\n{product_name}"]

        for label, value in (
            ("Brand", identity.get("brand")),
            ("Franchise", identity.get("franchise")),
            ("Collaboration partner", identity.get("collaboration_partner")),
        ):
            if value:
                lines.append(f"{label}:\n{clean_text(str(value))}")

        if release_details.get("status"):
            lines.append(f"Status:\n{release_details['status']}")

        if release_details.get("release_date"):
            lines.append(f"Release date:\n{release_details['release_date']}")

        if retail_details.get("required_spend") is not None:
            lines.append(
                f"Required spend:\n{_money(retail_details['required_spend'], currency)}"
            )

        if retail_details.get("retail_price") is not None:
            lines.append(
                f"Retail price:\n{_money(retail_details['retail_price'], currency)}"
            )

        if retail_details.get("purchase_limit") is not None:
            lines.append(f"Purchase limit:\n{retail_details['purchase_limit']} per order")

        characteristic_sentences = [
            _humanize_flag(key) for key, value in collector_characteristics.items() if value
        ]
        if characteristic_sentences:
            lines.append("Collector characteristics:\n" + "; ".join(characteristic_sentences) + ".")

        acquisition_sentences = [
            _humanize_flag(key) for key, value in acquisition_details.items() if value
        ]
        if acquisition_sentences:
            lines.append("Acquisition requirements:\n" + "; ".join(acquisition_sentences) + ".")

        for i, observation in enumerate(market_observations):
            price = observation.get("price")
            if price is None:
                continue
            kind = (observation.get("kind") or "").strip().lower()
            scope = observation.get("unit_scope") or "item"
            money = _money(price, currency)

            if kind == "sold":
                lines.append(f"Market observation:\nA {scope} sold for {money}.")
            else:
                lines.append(
                    f"Market observation:\nA {scope} is asking {money} "
                    f"(not confirmed sold)."
                )

        if evidence_excerpts:
            lines.append("Evidence excerpts:\n" + "\n".join(
                clean_text(excerpt) for excerpt in evidence_excerpts
            ))

        body = "\n\n".join(lines)

        transformations.append(record_transformation(
            "body", None, body, "structured_to_text",
            "Structured collector report sections assembled into a "
            "deterministic, labeled text representation for Module 2.",
        ))

        source_type, _ = normalize_source_type(source_details.get("source_type"))

        fields = {
            "title": product_name,
            "body": body,
            "source_name": normalize_source_name(source_details.get("source_name")),
            "source_type": source_type,
            "source_url": normalize_url(
                source_details.get("source_url"), config.supported_url_schemes,
            )[0],
            "author": source_details.get("author"),
            "published_at": release_details.get("announcement_date"),
            "brand_hint": identity.get("brand"),
            "franchise_hint": identity.get("franchise"),
        }

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "schema_version": payload.get("schema_version"),
            "confidence": payload.get("confidence"),
            "status": payload.get("status"),
            "collector_characteristics": payload.get("collector_characteristics"),
            "acquisition_details": payload.get("acquisition_details"),
            "market_observations": payload.get("market_observations"),
        }

    def fingerprint(self, payload):
        identity = payload.get("product_identity") or {}
        source_details = payload.get("source_details") or {}
        return compute_fingerprint(
            canonical_url=source_details.get("source_url"),
            source_id=identity.get("product_name"),
            title=identity.get("product_name"),
            content=str(payload.get("evidence_excerpts")),
            source_name=source_details.get("source_name"),
            published_at=(payload.get("release_details") or {}).get("announcement_date"),
        )


def _money(value, currency):
    symbol = _MONEY_SYMBOLS.get(currency, "")
    return f"{symbol}{value:g}" if symbol else f"{value:g} {currency}"


def _humanize_flag(key):
    return key.replace("_", " ")
