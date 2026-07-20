"""
Raw source input model for Module 2 (Collector Signal Detection).

A RawSourceInput represents one piece of raw text Atlas observed -
an announcement, a retailer page, a community post, an event notice -
before any interpretation happens. Nothing in this file inspects or
scores the text; it only holds it and its provenance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RawSourceInput:
    title: str
    body: str

    source_name: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    published_at: str | None = None
    discovered_at: str | None = None

    author: str | None = None
    retailer: str | None = None
    brand_hint: str | None = None
    franchise_hint: str | None = None

    raw_metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self):
        if not self.discovered_at:
            self.discovered_at = (
                datetime.now(timezone.utc)
                .isoformat()
            )

    @property
    def full_text(self):
        """
        The title and body concatenated for detectors that don't
        need to distinguish which field a match came from.
        """
        parts = [
            part
            for part in (self.title, self.body)
            if part
        ]

        return "\n".join(parts)
