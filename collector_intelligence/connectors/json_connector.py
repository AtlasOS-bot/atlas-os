"""
JSONConnector - generic JSON endpoint. Since arbitrary JSON has no
inherent product/article/listing shape, the source descriptor must
say which Module 5 adapter the payload maps to (`adapter_target`) -
Atlas cannot guess that from structure alone without risking a
misinterpretation. An optional `items_path` (list of keys) descends
into the parsed JSON to find the list of items to iterate; without
it, the whole document is treated as a single item.
"""

from collector_intelligence.connector_base import Connector
from collector_intelligence.connector_models import ConnectorError
from collector_intelligence.connector_parsing import parse_json

_VALID_ADAPTER_TARGETS = frozenset({
    "manual_text", "generic_article", "retailer_product", "marketplace_listing",
    "social_post", "rss_item", "event_listing", "structured_collector_report",
})


class JSONConnector(Connector):
    name = "json_connector"
    version = "1.0.0"
    supported_source_types = ("json",)

    def supports(self, source_descriptor):
        return source_descriptor.get("type") in self.supported_source_types

    def validate_config(self, source_descriptor, config):
        errors = super().validate_config(source_descriptor, config)

        adapter_target = source_descriptor.get("adapter_target")
        if not adapter_target:
            errors.append(ConnectorError(
                error_type="CONFIG_INVALID",
                message="json_connector requires 'adapter_target' - which "
                        "Module 5 adapter this JSON payload should be routed to.",
                recoverable=False,
            ))
        elif adapter_target not in _VALID_ADAPTER_TARGETS:
            errors.append(ConnectorError(
                error_type="CONFIG_INVALID",
                message=f"Unknown adapter_target {adapter_target!r}.",
                recoverable=False,
            ))

        return errors

    def parse(self, fetch_result, source_descriptor):
        data = parse_json(fetch_result.body)

        items_path = source_descriptor.get("items_path")
        if items_path:
            node = data
            for key in items_path:
                if isinstance(node, dict) and key in node:
                    node = node[key]
                else:
                    node = None
                    break
            data = node

        if isinstance(data, list):
            return data

        if data is None:
            return []

        return [data]

    def normalize(self, parsed_item, source_descriptor):
        return dict(parsed_item) if isinstance(parsed_item, dict) else {"value": parsed_item}

    def build_ingestion_payload(self, normalized_item, source_descriptor):
        return normalized_item, source_descriptor["adapter_target"]
