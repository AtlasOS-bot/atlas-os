from dataclasses import dataclass


@dataclass
class RawContent:
    source_name: str
    url: str
    content: str | None
    fetched_at: str
    status: int | None
    content_type: str | None
