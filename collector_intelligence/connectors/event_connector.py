"""
EventConnector - event/convention pages. Reads schema.org JSON-LD
Event markup when present; falls back to page title/body otherwise.
"""

from collector_intelligence.connector_base import Connector
from collector_intelligence.connector_parsing import find_json_ld_of_type, parse_html


class EventConnector(Connector):
    name = "event_connector"
    version = "1.0.0"
    supported_source_types = ("event_page",)

    def supports(self, source_descriptor):
        return source_descriptor.get("type") in self.supported_source_types

    def parse(self, fetch_result, source_descriptor):
        return [parse_html(fetch_result.body)]

    def normalize(self, parsed_item, source_descriptor):
        event = find_json_ld_of_type(parsed_item.get("json_ld") or [], "Event")

        event_name = (
            (event or {}).get("name")
            or parsed_item.get("h1")
            or parsed_item.get("title")
            or ""
        )

        location = (event or {}).get("location") if event else None
        venue = location.get("name") if isinstance(location, dict) else None

        organizer = (event or {}).get("organizer") if event else None
        organizer_name = organizer.get("name") if isinstance(organizer, dict) else (
            source_descriptor.get("source_name")
        )

        return {
            "event_name": event_name,
            "organizer": organizer_name,
            "event_url": source_descriptor["url"],
            "venue": venue,
            "event_start": (event or {}).get("startDate"),
            "event_end": (event or {}).get("endDate"),
            "announcement_text": (event or {}).get("description") or parsed_item.get("body") or "",
        }

    def build_ingestion_payload(self, normalized_item, source_descriptor):
        return normalized_item, "event_listing"
