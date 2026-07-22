"""
AnnouncementConnector - static official announcement / convention
announcement pages. Same HTML parsing as HTMLConnector, but defaults
source_type to OFFICIAL rather than leaving it to the caller, since
that's specifically what this connector is for.
"""

from collector_intelligence.connector_base import Connector
from collector_intelligence.connector_parsing import parse_html


class AnnouncementConnector(Connector):
    name = "announcement_connector"
    version = "1.0.0"
    supported_source_types = ("announcement",)

    def supports(self, source_descriptor):
        return source_descriptor.get("type") in self.supported_source_types

    def parse(self, fetch_result, source_descriptor):
        return [parse_html(fetch_result.body)]

    def normalize(self, parsed_item, source_descriptor):
        return {
            "title": parsed_item.get("title") or parsed_item.get("h1") or "",
            "body": parsed_item.get("body") or "",
            "source_name": source_descriptor.get("source_name"),
            "source_type": source_descriptor.get("source_type") or "OFFICIAL",
            "source_url": source_descriptor["url"],
            "published_at": source_descriptor.get("published_at"),
            "author": source_descriptor.get("author"),
        }

    def build_ingestion_payload(self, normalized_item, source_descriptor):
        return normalized_item, "generic_article"
