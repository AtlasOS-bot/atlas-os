"""
RetailerPageConnector - public product pages. Reads schema.org
JSON-LD Product markup (a general, widely-adopted convention, not a
site-specific scraper) when present; falls back to the page title and
body text when it isn't. Never invents a price/availability that
wasn't actually in the page.
"""

from collector_intelligence.connector_base import Connector
from collector_intelligence.connector_parsing import find_json_ld_of_type, parse_html


class RetailerPageConnector(Connector):
    name = "retailer_page_connector"
    version = "1.0.0"
    supported_source_types = ("retailer_page",)

    def supports(self, source_descriptor):
        return source_descriptor.get("type") in self.supported_source_types

    def parse(self, fetch_result, source_descriptor):
        return [parse_html(fetch_result.body)]

    def normalize(self, parsed_item, source_descriptor):
        product = find_json_ld_of_type(parsed_item.get("json_ld") or [], "Product")

        product_name = (
            (product or {}).get("name")
            or parsed_item.get("h1")
            or parsed_item.get("title")
            or ""
        )

        offers = (product or {}).get("offers") if product else None
        if isinstance(offers, list):
            offers = offers[0] if offers else None

        retail_price = None
        currency = None
        availability = None

        if isinstance(offers, dict):
            retail_price = offers.get("price") or offers.get("priceSpecification", {}).get("price")
            currency = offers.get("priceCurrency")
            raw_availability = offers.get("availability") or ""
            if "InStock" in raw_availability:
                availability = "In stock"
            elif "OutOfStock" in raw_availability:
                availability = "Out of stock"
            elif raw_availability:
                availability = raw_availability.rsplit("/", 1)[-1]

        return {
            "product_name": product_name,
            "retailer": source_descriptor.get("retailer") or source_descriptor.get("source_name"),
            "retail_price": retail_price,
            "currency": currency,
            "availability": availability,
            "sku": (product or {}).get("sku"),
            "description": (product or {}).get("description") or parsed_item.get("body") or "",
            "url": source_descriptor["url"],
        }

    def build_ingestion_payload(self, normalized_item, source_descriptor):
        return normalized_item, "retailer_product"
