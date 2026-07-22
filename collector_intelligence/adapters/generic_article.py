"""
GenericArticleAdapter - official announcements, press releases, news
articles, event announcements: anything with a title, body/content,
and standard article provenance fields.
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    html_to_text,
    normalize_source_name,
    normalize_source_type,
    normalize_url,
)
from collector_intelligence.ingestion_validation import (
    validate_non_empty_content,
    validate_source_type,
    validate_timestamp,
    validate_url,
)

_SIGNATURE_FIELDS = (
    "title", "body", "content", "source_name", "source_url", "published_at", "author",
)


class GenericArticleAdapter(SourceAdapter):
    name = "generic_article"
    version = "1.0.0"
    supported_payload_types = (dict,)
    supported_source_types = ("OFFICIAL", "PRESS_RELEASE", "NEWS", "EVENT")

    def can_handle(self, payload):
        if not isinstance(payload, dict):
            return False
        has_title = bool(payload.get("title"))
        has_body = bool(payload.get("body") or payload.get("content"))
        # Retailer/marketplace-specific fields mean a more specific
        # adapter should claim this payload instead.
        looks_structured_elsewhere = bool(
            payload.get("retail_price") or payload.get("listing_url")
            or payload.get("sku") or payload.get("platform")
        )
        return has_title and has_body and not looks_structured_elsewhere

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []

        present = [f for f in _SIGNATURE_FIELDS if payload.get(f)]
        confidence = min(0.5 + 0.08 * len(present), 0.9)
        return confidence, [
            f"Article-shaped payload with fields: {', '.join(present)}"
        ]

    def _body(self, payload):
        return payload.get("body") or payload.get("content") or ""

    def validate(self, payload, config):
        errors = []
        warnings = []

        errors.extend(validate_non_empty_content(payload.get("title"), self._body(payload)))

        _, url_issues = validate_url(payload.get("source_url"), "source_url", config)
        errors.extend(i for i in url_issues if i.severity == "ERROR")
        warnings.extend(i for i in url_issues if i.severity == "WARNING")

        _, ts_issues = validate_timestamp(payload.get("published_at"), "published_at")
        warnings.extend(ts_issues)

        _, type_issues = validate_source_type(payload.get("source_type"), "source_type")
        warnings.extend(type_issues)

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        body_raw = self._body(payload)
        body_stripped, was_html = html_to_text(body_raw)
        if was_html:
            transformations.append(record_transformation(
                "body", body_raw, body_stripped, "html_to_text",
                "Body contained HTML markup; converted to plain text.",
            ))
        body = clean_text(body_stripped)

        title = clean_text(payload.get("title") or "")

        source_type, _ = normalize_source_type(payload.get("source_type"))
        if not source_type:
            source_type = "NEWS"
            transformations.append(record_transformation(
                "source_type", None, "NEWS", "default_applied",
                "No source_type supplied; defaulted to NEWS (the most "
                "conservative article classification).",
            ))

        url, _ = normalize_url(payload.get("source_url"), config.supported_url_schemes)

        fields = {
            "title": title,
            "body": body,
            "source_name": normalize_source_name(payload.get("source_name")),
            "source_type": source_type,
            "source_url": url,
            "published_at": payload.get("published_at"),
            "author": payload.get("author"),
        }

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "article_categories": payload.get("categories"),
        }

    def fingerprint(self, payload):
        return compute_fingerprint(
            canonical_url=payload.get("source_url"),
            title=payload.get("title"),
            content=self._body(payload),
            source_name=payload.get("source_name"),
            published_at=payload.get("published_at"),
        )
