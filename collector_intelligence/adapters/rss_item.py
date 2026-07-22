"""
RSSItemAdapter - one item from an RSS/Atom-style feed. GUID is the
strongest identity signal for duplicate detection (the same GUID from
the same feed is definitionally the same item, even if its content is
later updated).
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    html_to_text,
    normalize_source_name,
    normalize_url,
)
from collector_intelligence.ingestion_validation import (
    validate_non_empty_content,
    validate_timestamp,
    validate_url,
)


class RSSItemAdapter(SourceAdapter):
    name = "rss_item"
    version = "1.0.0"
    supported_payload_types = (dict,)
    supported_source_types = ("NEWS",)

    def can_handle(self, payload):
        if not isinstance(payload, dict):
            return False
        has_feed_identity = bool(payload.get("feed_name") or payload.get("feed_url"))
        has_item_title = bool(payload.get("item_title") or payload.get("title"))
        has_item_identity = bool(payload.get("guid") or payload.get("item_link"))
        return has_feed_identity and has_item_title and has_item_identity

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []

        present = [
            f for f in ("guid", "summary", "content", "author", "categories")
            if payload.get(f)
        ]
        confidence = min(0.65 + 0.06 * len(present), 0.93)
        return confidence, [
            f"RSS-item-shaped payload (feed identity + item identity) with: "
            f"{', '.join(present) or 'no extras'}"
        ]

    def _body(self, payload):
        return payload.get("content") or payload.get("summary") or ""

    def validate(self, payload, config):
        errors = []
        warnings = []

        title = payload.get("item_title") or payload.get("title")
        errors.extend(validate_non_empty_content(title, self._body(payload)))

        _, url_issues = validate_url(payload.get("item_link"), "item_link", config)
        errors.extend(i for i in url_issues if i.severity == "ERROR")
        warnings.extend(i for i in url_issues if i.severity == "WARNING")

        _, feed_url_issues = validate_url(payload.get("feed_url"), "feed_url", config)
        warnings.extend(i for i in feed_url_issues if i.severity == "WARNING")

        _, ts_issues = validate_timestamp(payload.get("published_at"), "published_at")
        warnings.extend(ts_issues)

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        title = clean_text(payload.get("item_title") or payload.get("title") or "")

        body_raw = self._body(payload)
        body_stripped, was_html = html_to_text(body_raw)
        if was_html:
            transformations.append(record_transformation(
                "body", body_raw, body_stripped, "html_to_text",
                "RSS content/summary contained HTML markup; converted to "
                "plain text.",
            ))
        body = clean_text(body_stripped)

        fields = {
            "title": title,
            "body": body,
            "source_name": normalize_source_name(payload.get("feed_name")),
            "source_type": "NEWS",
            "source_url": normalize_url(payload.get("item_link"), config.supported_url_schemes)[0],
            "published_at": payload.get("published_at"),
            "author": payload.get("author"),
        }

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "feed_name": payload.get("feed_name"),
            "feed_url": payload.get("feed_url"),
            "guid": payload.get("guid"),
            "categories": payload.get("categories"),
        }

    def fingerprint(self, payload):
        return compute_fingerprint(
            guid=payload.get("guid"),
            canonical_url=payload.get("item_link") if not payload.get("guid") else None,
            title=payload.get("item_title") or payload.get("title"),
            content=self._body(payload),
            source_name=payload.get("feed_name"),
            published_at=payload.get("published_at"),
        )
