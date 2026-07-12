import importlib


MODULES = [
    "brain.atlas_brain",
    "brain.explanation_engine",

    "reasoning.engine",
    "reasoning.evidence",
    "reasoning.confidence",
    "reasoning.opportunity",
    "reasoning.urgency",
    "reasoning.resale",

    "signals.base",
    "signals.engine",

    "decision.decision_engine",

    "scouts.pokemon.collector",
    "scouts.pokemon.parser",
    "scouts.pokemon.rules",
    "scouts.pokemon.scorer",

    "scouts.nike.collector",
    "scouts.nike.parser",
    "scouts.nike.rules",
    "scouts.nike.scorer",
    "scouts.pokemon.sources",
"scouts.pokemon.internet_scout",
"scouts.pokemon.structured_data",
"popularity.models",
"popularity.pokemon",
"popularity.engine",
"scouts.pokemon.classifier",
"scouts.pokemon.enrichment",
"scouts.pokemon.collector_intelligence",
"signals.collector_value",
"scouts.pokemon.investment_intelligence",
"signals.investment_strategy",
"scouts.pokemon.identity",
"scouts.pokemon.consensus",
"signals.source_consensus",
"scouts.pokemon.state_tracker",
"scouts.pokemon.alert_intelligence",
"scouts.pokemon.alert_store",
"scouts.pokemon.alert_queue",
"scouts.pokemon.alert_brief",
"scouts.pokemon.release_calendar",
"scouts.pokemon.release_brief",
"scouts.pokemon.release_store",
"scouts.pokemon.product_details",
]


def test_imports():
    for module in MODULES:
        importlib.import_module(module)