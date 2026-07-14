import importlib


MODULES = [
    "atlas.daily_brief",
    "atlas.mission",
    "atlas.ranking",

    "brain.atlas_brain",
    "brain.explanation_engine",

    "decision.decision_engine",

    "learning.engine",
    "learning.models",
    "learning.statistics",
    "learning.storage",

    "market.aggregator",
    "market.cache",
    "market.ebay",
    "market.ebay_live",
    "market.engine",
    "market.manual",
    "market.models",
    "market.pricecharting",
    "market.provider",
    "market.roi",
    "market.router",
    "market.stockx",
    "market.tcgplayer",

    "patterns.engine",
    "patterns.history",
    "patterns.matcher",
    "patterns.scorer",

    "popularity.engine",
    "popularity.models",
    "popularity.pokemon",

    "reasoning.confidence",
    "reasoning.engine",
    "reasoning.evidence",
    "reasoning.opportunity",
    "reasoning.resale",
    "reasoning.urgency",

    "scouts.base.atlas_scout",

    "scouts.nike.collector",
    "scouts.nike.parser",
    "scouts.nike.rules",
    "scouts.nike.scorer",

    "scouts.pokemon.alert_brief",
    "scouts.pokemon.alert_intelligence",
    "scouts.pokemon.alert_queue",
    "scouts.pokemon.alert_store",
    "scouts.pokemon.classifier",
    "scouts.pokemon.collector",
    "scouts.pokemon.collector_intelligence",
    "scouts.pokemon.consensus",
    "scouts.pokemon.enrichment",
    "scouts.pokemon.identity",
    "scouts.pokemon.internet_scout",
    "scouts.pokemon.investment_intelligence",
    "scouts.pokemon.parser",
    "scouts.pokemon.product_details",
    "scouts.pokemon.release_brief",
    "scouts.pokemon.release_calendar",
    "scouts.pokemon.release_store",
    "scouts.pokemon.rules",
    "scouts.pokemon.scorer",
    "scouts.pokemon.sources",
    "scouts.pokemon.state_tracker",
    "scouts.pokemon.structured_data",

    "scouts.tcg.classifier",
    "scouts.tcg.enrichment",
    "scouts.tcg.intelligence",
    "scouts.tcg.profiles",

    "scouts.lorcana",
    "scouts.lorcana.collector",
    "scouts.lorcana.internet_scout",
    "scouts.lorcana.parser",
    "scouts.lorcana.sources",

    "signals.base",
    "signals.collaboration",
    "signals.collector_interest",
    "signals.collector_value",
    "signals.exclusive",
    "signals.historical_pattern",
    "signals.investment_strategy",
    "signals.limited_release",
    "signals.official_source",
    "signals.reprint",
    "signals.restock",
    "signals.shock_drop",
    "signals.source_consensus",
]


def test_imports():
    for module in MODULES:
        importlib.import_module(
            module
        )