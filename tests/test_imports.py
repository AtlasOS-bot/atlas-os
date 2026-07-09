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
]


def test_imports():
    for module in MODULES:
        importlib.import_module(module)