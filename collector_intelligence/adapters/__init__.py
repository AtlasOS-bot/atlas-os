from collector_intelligence.adapters.event_listing import EventListingAdapter
from collector_intelligence.adapters.generic_article import GenericArticleAdapter
from collector_intelligence.adapters.manual_text import ManualTextAdapter
from collector_intelligence.adapters.marketplace_listing import MarketplaceListingAdapter
from collector_intelligence.adapters.retailer_product import RetailerProductAdapter
from collector_intelligence.adapters.rss_item import RSSItemAdapter
from collector_intelligence.adapters.social_post import SocialPostAdapter
from collector_intelligence.adapters.structured_report import (
    StructuredCollectorReportAdapter,
)

__all__ = [
    "EventListingAdapter",
    "GenericArticleAdapter",
    "ManualTextAdapter",
    "MarketplaceListingAdapter",
    "RetailerProductAdapter",
    "RSSItemAdapter",
    "SocialPostAdapter",
    "StructuredCollectorReportAdapter",
    "build_default_registry",
]


def build_default_registry():
    from collector_intelligence.adapter_registry import AdapterRegistry

    registry = AdapterRegistry()

    for adapter_cls in (
        StructuredCollectorReportAdapter,
        RetailerProductAdapter,
        MarketplaceListingAdapter,
        EventListingAdapter,
        RSSItemAdapter,
        SocialPostAdapter,
        GenericArticleAdapter,
        ManualTextAdapter,
    ):
        registry.register(adapter_cls())

    return registry
