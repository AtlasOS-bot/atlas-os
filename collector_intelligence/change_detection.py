"""
Atlas v21 - Module 6: change detection between fetches of the same URL.

Distinguishes a purely cosmetic timestamp update ("last checked: ...")
from a real content change, and flags cross-URL duplicates using the
cache's full hash index.
"""

import re

from collector_intelligence.connector_cache import compute_content_hash
from collector_intelligence.connector_models import ChangeDetectionResult

_TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)


def compute_semantic_hash(text):
    """Content hash with ISO-timestamp-shaped substrings stripped, so a
    page whose only change is a "last updated" stamp doesn't register
    as a real content change."""
    if text is None:
        return None
    stripped = _TIMESTAMP_PATTERN.sub("", text)
    return compute_content_hash(stripped)


def detect_change(url, current_body, cache, check_cross_source_duplicates=True):
    previous = cache.get(url)

    if current_body is None or current_body.strip() == "":
        if previous is not None:
            return ChangeDetectionResult(
                status="REMOVED",
                current_hash=None,
                previous_hash=previous.content_hash,
                previous_fetched_at=previous.fetched_at,
                explanation=f"{url} previously had content but now returns none.",
            )
        return ChangeDetectionResult(
            status="UNCHANGED",
            explanation=f"{url} has never had content.",
        )

    current_hash = compute_content_hash(current_body)

    if previous is None:
        if check_cross_source_duplicates:
            known_hashes = cache.all_hashes()
            duplicate_of = next(
                (other_url for other_url, h in known_hashes.items()
                 if h == current_hash and other_url != url),
                None,
            )
            if duplicate_of:
                return ChangeDetectionResult(
                    status="DUPLICATE",
                    current_hash=current_hash,
                    explanation=f"Content is identical to already-cached {duplicate_of!r}.",
                )

        return ChangeDetectionResult(
            status="NEW",
            current_hash=current_hash,
            explanation=f"No prior fetch recorded for {url}.",
        )

    if previous.content_hash == current_hash:
        return ChangeDetectionResult(
            status="UNCHANGED",
            current_hash=current_hash,
            previous_hash=previous.content_hash,
            previous_fetched_at=previous.fetched_at,
            explanation="Content hash matches the previous fetch exactly.",
        )

    previous_semantic = compute_semantic_hash(previous.body)
    current_semantic = compute_semantic_hash(current_body)

    if previous_semantic == current_semantic:
        return ChangeDetectionResult(
            status="TIMESTAMP_ONLY",
            current_hash=current_hash,
            previous_hash=previous.content_hash,
            previous_fetched_at=previous.fetched_at,
            explanation="Only timestamp-shaped substrings differ; "
                        "content is otherwise identical.",
        )

    return ChangeDetectionResult(
        status="CHANGED",
        current_hash=current_hash,
        previous_hash=previous.content_hash,
        previous_fetched_at=previous.fetched_at,
        explanation="Content hash differs from the previous fetch.",
    )
