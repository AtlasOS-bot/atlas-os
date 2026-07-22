"""
Atlas v21 - Module 5: deterministic payload fingerprinting.

Two-part fingerprint:
- identity_key: a stable "this is the same real-world source" key
  (canonical URL, GUID, listing ID, or source ID - in that priority
  order). None if the payload carries no such identity.
- content_hash: a hash of the actual normalized content.

combined = identity_key + content_hash when an identity exists,
otherwise just the content hash. Two payloads with the SAME combined
fingerprint are exact duplicates. Two payloads with the same
identity_key but a DIFFERENT content_hash represent the same source
with updated content - not a duplicate, an update.
"""

import hashlib

from collector_intelligence.normalize import normalize_text


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def compute_fingerprint(
    canonical_url=None,
    guid=None,
    listing_id=None,
    source_id=None,
    title=None,
    content=None,
    source_name=None,
    published_at=None,
):
    identity_key = None

    for label, value in (
        ("url", canonical_url),
        ("guid", guid),
        ("listing", listing_id),
        ("source", source_id),
    ):
        if value:
            identity_key = f"{label}:{normalize_text(str(value)) or str(value).strip().lower()}"
            break

    content_parts = [
        normalize_text(title) or "",
        normalize_text(source_name) or "",
        (published_at or "").strip(),
        (normalize_text(content) or "")[:2000],
    ]
    content_hash = _hash("|".join(content_parts))

    combined = f"{identity_key}#{content_hash}" if identity_key else content_hash

    return identity_key, content_hash, combined


def content_similarity(text_a, text_b):
    """
    Cheap word-overlap similarity in [0, 1] - good enough to flag
    "similar but not identical" content without pulling in an NLP
    dependency. Not used for hard duplicate decisions.
    """
    words_a = set((normalize_text(text_a) or "").split())
    words_b = set((normalize_text(text_b) or "").split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union) if union else 0.0
