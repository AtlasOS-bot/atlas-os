"""
RSSConnector - RSS 2.0 and Atom feeds. One feed fetch produces many
items, each routed to Module 5's rss_item adapter.
"""

from collector_intelligence.connector_base import Connector
from collector_intelligence.connector_parsing import ParsingError, parse_rss_or_atom


class RSSConnector(Connector):
    name = "rss_connector"
    version = "1.0.0"
    supported_source_types = ("rss", "atom")

    def supports(self, source_descriptor):
        return source_descriptor.get("type") in self.supported_source_types

    def parse(self, fetch_result, source_descriptor):
        try:
            feed = parse_rss_or_atom(fetch_result.body)
        except ParsingError as exc:
            raise exc

        items = feed["items"]
        for item in items:
            item["_feed_title"] = feed.get("feed_title")
            item["_feed_link"] = feed.get("feed_link")

        return items

    def normalize(self, parsed_item, source_descriptor):
        return {
            "feed_name": source_descriptor.get("feed_name") or parsed_item.get("_feed_title"),
            "feed_url": parsed_item.get("_feed_link") or source_descriptor["url"],
            "item_title": parsed_item.get("title"),
            "item_link": parsed_item.get("link"),
            "summary": parsed_item.get("summary"),
            "content": parsed_item.get("content"),
            "published_at": parsed_item.get("published_at"),
            "author": parsed_item.get("author"),
            "guid": parsed_item.get("guid"),
            "categories": parsed_item.get("categories") or [],
        }

    def build_ingestion_payload(self, normalized_item, source_descriptor):
        return normalized_item, "rss_item"
