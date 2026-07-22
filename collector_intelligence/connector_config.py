"""
Atlas v21 - Module 6: connector configuration.

Every numeric/behavioral threshold the connector framework uses lives
here, with support for per-connector overrides layered on top of a
shared default.
"""

import dataclasses
from dataclasses import dataclass, field


DEFAULT_ALLOWED_MIME_TYPES = frozenset({
    "text/html", "application/xhtml+xml",
    "application/xml", "text/xml", "application/rss+xml", "application/atom+xml",
    "application/json", "text/plain",
})


@dataclass
class ConnectorConfig:
    timeout_seconds: float = 15.0

    max_retries: int = 3
    retry_backoff_base_seconds: float = 0.5
    retry_backoff_max_seconds: float = 8.0

    user_agent: str = "AtlasCollectorBot/1.0 (+https://atlas.invalid/bot)"

    rate_limit_per_minute: int = 30

    max_payload_bytes: int = 5_000_000

    use_etag: bool = True
    use_last_modified: bool = True
    cache_ttl_seconds: float = 900.0

    follow_redirects: bool = True
    max_redirects: int = 5

    allowed_mime_types: frozenset = field(
        default_factory=lambda: frozenset(DEFAULT_ALLOWED_MIME_TYPES)
    )

    verify_ssl: bool = True

    # {connector_name: {field_name: value}} - applied on top of these
    # defaults via for_connector().
    overrides: dict = field(default_factory=dict)

    def for_connector(self, name):
        override = self.overrides.get(name)
        if not override:
            return self
        return dataclasses.replace(self, **override)
