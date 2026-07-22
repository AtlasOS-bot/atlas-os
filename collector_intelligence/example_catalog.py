"""
Atlas v21 - Module 7: a small but realistic example catalog.

Every URL uses the example.test domain (RFC 2606 reserved for
documentation/examples) - nothing here is ever fetched, in tests or
otherwise, by this module.

Includes the required Round1 scenario:
- one_piece_tcg watches a Bandai official announcement AND a Round1
  retailer announcement.
- broad_tcg shares the same Bandai source.
- general_retail_drops shares the same Round1 source.
- a marketplace export source supplies complete-set sold evidence
  (never a one-pack sold source).
"""


def build_example_catalog_data():
    return {
        "catalog_version": "1.0.0",
        "schema_version": "1.0.0",
        "environment": "development",
        "categories": [
            {"category_id": "tcg", "name": "Trading Card Games"},
            {"category_id": "collectibles", "name": "General Collectibles", "parent_category_id": None},
            {"category_id": "events", "name": "Conventions & Events"},
        ],
        "brands": [
            {
                "brand_id": "pokemon", "name": "Pokemon", "categories": ["tcg"],
                "official_domains": ["pokemon.com", "pokemoncenter.com"],
                "aliases": ["Pokemon TCG", "The Pokemon Company"],
            },
            {
                "brand_id": "bandai", "name": "Bandai", "categories": ["tcg", "collectibles"],
                "official_domains": ["bandai.com"],
                "aliases": ["Bandai Namco"],
            },
            {
                "brand_id": "target", "name": "Target", "categories": ["collectibles"],
                "official_domains": ["target.com"],
            },
            {
                "brand_id": "best_buy", "name": "Best Buy", "categories": ["collectibles"],
                "official_domains": ["bestbuy.com"],
            },
            {
                "brand_id": "round1", "name": "Round1", "categories": ["collectibles"],
                "official_domains": ["round1usa.com"],
            },
            {
                "brand_id": "anime_expo", "name": "Anime Expo", "categories": ["events"],
                "official_domains": ["anime-expo.org"],
            },
        ],
        "scouts": [
            {
                "scout_id": "pokemon", "name": "Pokemon Scout",
                "description": "Watches Pokemon TCG official/retailer sources.",
                "priority": "critical",
                "categories": ["tcg"], "brands": ["pokemon"],
                "source_ids": ["pokemon_official_rss", "pokemon_center_announcements"],
                "default_schedule": {"mode": "hourly"},
                "owner": "collector-intelligence-team",
            },
            {
                "scout_id": "one_piece_tcg", "name": "One Piece TCG Scout",
                "description": "Watches One Piece TCG official and retailer sources.",
                "priority": "critical",
                "categories": ["tcg"], "brands": ["bandai", "round1"],
                "source_ids": ["bandai_one_piece_announcements", "round1_promo_announcements"],
                "default_schedule": {"mode": "hourly"},
                "owner": "collector-intelligence-team",
            },
            {
                "scout_id": "broad_tcg", "name": "Broad TCG Scout",
                "description": "Cross-brand trading card game coverage.",
                "priority": "high",
                "categories": ["tcg"], "brands": ["pokemon", "bandai"],
                "source_ids": ["bandai_one_piece_announcements"],
                "default_schedule": {"mode": "daily"},
                "owner": "collector-intelligence-team",
            },
            {
                "scout_id": "collector_events", "name": "Collector Events Scout",
                "description": "Conventions and collector meetups.",
                "priority": "medium",
                "categories": ["events"], "brands": ["anime_expo"],
                "source_ids": ["anime_expo_event_page"],
                "default_schedule": {"mode": "daily"},
                "owner": "collector-intelligence-team",
            },
            {
                "scout_id": "general_retail_drops", "name": "General Retail Drops Scout",
                "description": "Cross-brand retailer collectible drops.",
                "priority": "high",
                "categories": ["collectibles"], "brands": ["target", "best_buy", "round1"],
                "source_ids": [
                    "target_collectibles_page", "best_buy_collectibles_page",
                    "round1_promo_announcements", "marketplace_sold_export",
                ],
                "default_schedule": {"mode": "daily"},
                "owner": "collector-intelligence-team",
            },
        ],
        "sources": [
            {
                "source_id": "pokemon_official_rss",
                "name": "Pokemon Official News RSS",
                "source_type": "rss_feed", "authority_level": "official_primary",
                "connector_type": "rss_connector",
                "url": "https://news.example.test/pokemon/feed.xml",
                "brand_id": "pokemon", "scout_ids": ["pokemon"],
                "category_ids": ["tcg"],
                "schedule": {"mode": "hourly"},
                "lifecycle_state": "active",
                "expected_evidence": {
                    "evidence_types": ["announcement"], "official_status": "confirmed",
                    "supports_release_date": True,
                },
            },
            {
                "source_id": "pokemon_center_announcements",
                "name": "Pokemon Center Announcement Page",
                "source_type": "official_announcement", "authority_level": "official_primary",
                "connector_type": "announcement_connector",
                "url": "https://pokemoncenter.example.test/news",
                "brand_id": "pokemon", "scout_ids": ["pokemon"],
                "category_ids": ["tcg"],
                "schedule": {"mode": "hourly"},
                "lifecycle_state": "active",
                "expected_evidence": {
                    "evidence_types": ["announcement"], "official_status": "confirmed",
                    "supports_release_date": True, "supports_availability": True,
                },
            },
            {
                "source_id": "bandai_one_piece_announcements",
                "name": "Bandai Official One Piece Announcements",
                "source_type": "official_announcement", "authority_level": "official_primary",
                "connector_type": "announcement_connector",
                "url": "https://bandai.example.test/one-piece/news",
                "brand_id": "bandai", "scout_ids": ["one_piece_tcg", "broad_tcg"],
                "category_ids": ["tcg"],
                "schedule": {"mode": "hourly"},
                "lifecycle_state": "active",
                "expected_evidence": {
                    "evidence_types": ["announcement", "collaboration"],
                    "official_status": "confirmed",
                    "supports_release_date": True, "supports_purchase_limits": True,
                },
            },
            {
                "source_id": "round1_promo_announcements",
                "name": "Round1 Promotional Announcement Page",
                "source_type": "retailer_product_page", "authority_level": "authorized_retailer",
                "connector_type": "retailer_page_connector",
                "url": "https://round1.example.test/promotions/one-piece",
                "brand_id": "round1", "scout_ids": ["one_piece_tcg", "general_retail_drops"],
                "category_ids": ["tcg", "collectibles"],
                "schedule": {"mode": "daily"},
                "lifecycle_state": "active",
                "expected_evidence": {
                    "evidence_types": ["retail_price", "availability"],
                    "official_status": "confirmed",
                    "supports_availability": True, "supports_purchase_limits": True,
                },
            },
            {
                "source_id": "target_collectibles_page",
                "name": "Target Collectibles Product Source",
                "source_type": "retailer_product_page", "authority_level": "authorized_retailer",
                "connector_type": "retailer_page_connector",
                "url": "https://target.example.test/collectibles",
                "brand_id": "target", "scout_ids": ["general_retail_drops"],
                "category_ids": ["collectibles"],
                "schedule": {"mode": "daily"},
                "lifecycle_state": "active",
                "expected_evidence": {
                    "evidence_types": ["retail_price", "availability"],
                    "supports_availability": True,
                },
            },
            {
                "source_id": "best_buy_collectibles_page",
                "name": "Best Buy Collectibles Source",
                "source_type": "retailer_product_page", "authority_level": "authorized_retailer",
                "connector_type": "retailer_page_connector",
                "url": "https://bestbuy.example.test/collectibles",
                "brand_id": "best_buy", "scout_ids": ["general_retail_drops"],
                "category_ids": ["collectibles"],
                "schedule": {"mode": "daily"},
                "lifecycle_state": "proposed",
                "expected_evidence": {
                    "evidence_types": ["retail_price", "availability"],
                    "supports_availability": True,
                },
            },
            {
                "source_id": "anime_expo_event_page",
                "name": "Anime Expo Event Source",
                "source_type": "event_listing", "authority_level": "official_primary",
                "connector_type": "event_connector",
                "url": "https://anime-expo.example.test/events/collector-meetup",
                "brand_id": "anime_expo", "scout_ids": ["collector_events"],
                "category_ids": ["events"],
                "schedule": {"mode": "daily"},
                "lifecycle_state": "active",
                "expected_evidence": {
                    "evidence_types": ["event_details"], "official_status": "confirmed",
                    "supports_event_details": True,
                },
            },
            {
                "source_id": "marketplace_sold_export",
                "name": "Marketplace Sold-Data Export (Manual)",
                "source_type": "marketplace_sold_data", "authority_level": "marketplace_confirmed_sale",
                "connector_type": "json_connector",
                "connector_config": {"adapter_target": "marketplace_listing", "items_path": ["listings"]},
                "url": "https://marketplace-export.example.test/sold.json",
                "scout_ids": ["general_retail_drops"],
                "category_ids": ["tcg", "collectibles"],
                "schedule": {"mode": "daily"},
                "lifecycle_state": "active",
                "expected_evidence": {
                    "evidence_types": ["sold_price"],
                    "official_status": "confirmed",
                    "price_kind": "sold",
                    "expected_unit_scope": "complete_set",
                    "supports_market_price": True,
                    "notes": "Confirmed-sale export scoped to complete sets - never "
                             "a single-pack sold source.",
                },
            },
        ],
    }


def load_example_catalog(config=None):
    from collector_intelligence.catalog_loading import load_catalog
    return load_catalog(build_example_catalog_data(), config=config)
