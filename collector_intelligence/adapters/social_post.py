"""
SocialPostAdapter - a social media post. Always produces
source_type="SOCIAL", regardless of a verified-account flag - being
verified doesn't make a post an official brand statement, so it must
never be silently upgraded to OFFICIAL. Engagement metrics are kept as
metadata only; they are never turned into demand-claiming prose.
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    html_to_text,
    normalize_platform_name,
    normalize_url,
    parse_boolean,
)
from collector_intelligence.ingestion_validation import (
    validate_non_empty_content,
    validate_timestamp,
    validate_url,
)


class SocialPostAdapter(SourceAdapter):
    name = "social_post"
    version = "1.0.0"
    supported_payload_types = (dict,)
    supported_source_types = ("SOCIAL",)

    def can_handle(self, payload):
        if not isinstance(payload, dict):
            return False
        return bool(payload.get("platform") and payload.get("text"))

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []

        present = [
            f for f in ("account_name", "posted_at", "engagement", "url")
            if payload.get(f) is not None
        ]
        confidence = min(0.65 + 0.06 * len(present), 0.92)
        return confidence, [
            f"Social-post-shaped payload (platform + text) with: {', '.join(present) or 'no extras'}"
        ]

    def validate(self, payload, config):
        errors = []
        warnings = []

        errors.extend(validate_non_empty_content(None, payload.get("text"), field_label="text"))

        _, url_issues = validate_url(payload.get("url"), "url", config)
        errors.extend(i for i in url_issues if i.severity == "ERROR")
        warnings.extend(i for i in url_issues if i.severity == "WARNING")

        _, ts_issues = validate_timestamp(payload.get("posted_at"), "posted_at")
        warnings.extend(ts_issues)

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        text_raw = payload.get("text") or ""
        text_stripped, was_html = html_to_text(text_raw)
        if was_html:
            transformations.append(record_transformation(
                "text", text_raw, text_stripped, "html_to_text",
                "Post text contained HTML markup; converted to plain text.",
            ))
        body = clean_text(text_stripped)

        if payload.get("attached_text_description"):
            body = (
                body + "\n\n" + clean_text(payload["attached_text_description"])
            ).strip()

        platform = normalize_platform_name(payload.get("platform"))
        account_name = clean_text(payload.get("account_name") or "") or None

        title = f"{platform} post by {account_name}" if account_name else f"{platform} post"

        is_repost = parse_boolean(payload.get("is_repost")) or parse_boolean(payload.get("is_quote_post"))
        if is_repost:
            title = f"[Repost] {title}"

        fields = {
            "title": title,
            "body": body,
            "source_name": account_name or platform,
            "source_type": "SOCIAL",
            "source_url": normalize_url(payload.get("url"), config.supported_url_schemes)[0],
            "published_at": payload.get("posted_at"),
            "author": account_name,
        }

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "platform": normalize_platform_name(payload.get("platform")),
            "verified_account": parse_boolean(payload.get("verified")),
            "is_repost": parse_boolean(payload.get("is_repost")),
            "is_quote_post": parse_boolean(payload.get("is_quote_post")),
            # Retained for context only - never treated as demand evidence.
            "engagement": payload.get("engagement"),
            "engagement_is_not_demand_evidence": True,
        }

    def fingerprint(self, payload):
        return compute_fingerprint(
            canonical_url=payload.get("url"),
            title=payload.get("account_name"),
            content=payload.get("text"),
            source_name=payload.get("platform"),
            published_at=payload.get("posted_at"),
        )
