from collector_intelligence.connectors.announcement_connector import AnnouncementConnector
from collector_intelligence.connectors.event_connector import EventConnector
from collector_intelligence.connectors.html_connector import HTMLConnector
from collector_intelligence.connectors.json_connector import JSONConnector
from collector_intelligence.connectors.retailer_page_connector import RetailerPageConnector
from collector_intelligence.connectors.rss_connector import RSSConnector
from collector_intelligence.connectors.xml_connector import XMLConnector

__all__ = [
    "AnnouncementConnector",
    "EventConnector",
    "HTMLConnector",
    "JSONConnector",
    "RetailerPageConnector",
    "RSSConnector",
    "XMLConnector",
    "build_default_manager",
]


def build_default_manager(http_client=None, cache=None):
    from collector_intelligence.connector_registry import ConnectorManager

    manager = ConnectorManager(http_client=http_client, cache=cache)

    for connector_cls in (
        RSSConnector, HTMLConnector, JSONConnector, XMLConnector,
        AnnouncementConnector, RetailerPageConnector, EventConnector,
    ):
        manager.register(connector_cls())

    return manager
