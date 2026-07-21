"""
Atlas v21 - Module 3: data models for scoring context and results.

ScoringContext carries optional signals the caller may already know
(franchise strength, category benchmarks, comparable products, a
current timestamp, analyst notes) that decision_engine can use to
sharpen a score - never to invent one. Every field defaults to None
so an opportunity can be evaluated with zero context.

OpportunityEvaluation is the complete, explainable output of
evaluate_opportunity(). It is a standalone result object - it never
mutates the CollectorOpportunity it was built from.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ScoringContext:
    current_timestamp: str | None = None
    category_benchmarks: dict[str, Any] | None = None
    franchise_strength: float | None = None
    product_line_history: dict[str, Any] | None = None
    comparable_products: list[Any] = field(default_factory=list)

    # Direct field overrides applied to the final evaluation (e.g. an
    # analyst manually pins recommended_quantity). Applied last, after
    # every computed score and rule.
    overrides: dict[str, Any] = field(default_factory=dict)

    analyst_notes: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class OpportunityEvaluation:
    collector_score: float = 0.0
    flip_score: float = 0.0
    hold_score: float = 0.0
    scarcity_score: float = 0.0
    demand_score: float = 0.0
    hype_score: float = 0.0
    acquisition_score: float = 0.0
    risk_score: float = 0.0
    confidence_score: float = 0.0
    opportunity_score: float = 0.0

    recommendation: str = "WATCH"
    primary_strategy: str = "WATCH"
    recommended_quantity: int = 0
    target_buy_price: float | None = None
    target_sell_price: float | None = None
    estimated_profit: float | None = None
    estimated_roi_percent: float | None = None
    flip_time_horizon: str | None = None
    hold_time_horizon: str | None = None

    # {score_name: {"positives": [...], "negatives": [...], "notes": [...]}}
    score_explanation: dict[str, Any] = field(default_factory=dict)

    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    decision_summary: str = ""

    def to_dict(self):
        return asdict(self)
