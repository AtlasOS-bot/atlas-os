"""
ManualTextAdapter - the generic fallback. Accepts a plain string or a
loosely-structured dict (title/body/url/source info) such as a
copy-pasted announcement, social post, or a human-written field
report. Always the lowest-confidence adapter so more specific adapters
win when their fields are present.
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    html_to_text,
    normalize_source_name,
    normalize_source_type,
)
from collector_intelligence.ingestion_validation import (
    validate_non_empty_content,
    validate_source_type,
    validate_timestamp,
    validate_url,
)


class ManualTextAdapter(SourceAdapter):
    name = "manual_text"
    version = "1.0.0"
    supported_payload_types = (str, dict)
    supported_source_types = ()

    def can_handle(self, payload):
        if isinstance(payload, str):
            return bool(payload.strip())
        if isinstance(payload, dict):
            return bool(
                payload.get("text") or payload.get("body") or payload.get("title")
            )
        return False

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []
        return 0.25, [
            "Generic manual text/dict payload - lowest-priority fallback adapter"
        ]

    def _body_text(self, payload):
        if isinstance(payload, str):
            return payload
        return payload.get("body") or payload.get("text") or ""

    def validate(self, payload, config):
        errors = []
        warnings = []

        title = None if isinstance(payload, str) else payload.get("title")
        body = self._body_text(payload)

        errors.extend(validate_non_empty_content(title, body))

        if isinstance(payload, dict):
            url = payload.get("url") or payload.get("source_url")
            _, url_issues = validate_url(url, "url", config)
            errors.extend(i for i in url_issues if i.severity == "ERROR")
            warnings.extend(i for i in url_issues if i.severity == "WARNING")

            _, type_issues = validate_source_type(
                payload.get("source_type"), "source_type"
            )
            warnings.extend(type_issues)

            _, ts_issues = validate_timestamp(
                payload.get("published_at"), "published_at"
            )
            warnings.extend(ts_issues)

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        if isinstance(payload, str):
            body_raw = payload
            title_raw = ""
        else:
            title_raw = payload.get("title") or ""
            body_raw = self._body_text(payload)

        body_html_stripped, was_html = html_to_text(body_raw)
        if was_html:
            transformations.append(record_transformation(
                "body", body_raw, body_html_stripped, "html_to_text",
                "Body contained HTML markup; converted to plain text.",
            ))

        body = clean_text(body_html_stripped)
        if body != body_html_stripped:
            transformations.append(record_transformation(
                "body", body_html_stripped, body, "text_cleanup",
                "Whitespace/unicode/control-character cleanup.",
            ))

        title = clean_text(title_raw)

        fields = {"title": title, "body": body}

        if isinstance(payload, dict):
            source_type, _ = normalize_source_type(payload.get("source_type"))
            from collector_intelligence.ingestion_normalization import normalize_url

            url, _ = normalize_url(
                payload.get("url") or payload.get("source_url"),
                config.supported_url_schemes,
            )

            fields.update({
                "source_name": normalize_source_name(payload.get("source_name")),
                "source_type": source_type or "OTHER",
                "source_url": url,
                "published_at": payload.get("published_at"),
                "author": payload.get("author"),
                "retailer": payload.get("retailer"),
            })
        else:
            fields["source_type"] = "OTHER"

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "input_kind": "string" if isinstance(payload, str) else "dict",
            "manual_entry": True,
        }

    def fingerprint(self, payload):
        if isinstance(payload, str):
            return compute_fingerprint(content=payload)

        return compute_fingerprint(
            canonical_url=payload.get("url") or payload.get("source_url"),
            title=payload.get("title"),
            content=self._body_text(payload),
            source_name=payload.get("source_name"),
            published_at=payload.get("published_at"),
        )
