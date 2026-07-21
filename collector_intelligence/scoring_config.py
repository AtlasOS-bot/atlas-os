"""
Atlas v21 - Module 3: scoring configuration.

Every threshold, weight, and penalty the decision engine uses lives
here so behavior can be tuned without touching scoring logic. All
defaults are conservative on purpose - CRITICAL_BUY should be rare.
"""

from dataclasses import dataclass, field


@dataclass
class ScoringConfig:
    # Weighted contribution of each component score to opportunity_score.
    # "monetization_score" is max(flip_score, hold_score): a viable
    # opportunity only needs ONE credible exit strategy, so a strong
    # flip play is never dragged down by a (legitimately) unscored
    # hold angle, or vice versa. Deliberately excludes risk_score/
    # confidence_score, which act as a penalty and a ceiling instead
    # (see decision_engine.compute_opportunity_score).
    opportunity_weights: dict = field(
        default_factory=lambda: {
            "monetization_score": 0.35,
            "collector_score": 0.10,
            "scarcity_score": 0.12,
            "demand_score": 0.13,
            "acquisition_score": 0.15,
            "hype_score": 0.15,
        }
    )

    # How much of risk_score (0-100) is subtracted from the weighted
    # base opportunity_score. 0.3 means maximum risk removes 30 pts.
    risk_penalty_weight: float = 0.3

    # opportunity_score can never exceed confidence_score + this
    # margin - low-confidence opportunities are capped, not just
    # nudged down.
    confidence_cap_margin: float = 15.0

    # Minimum opportunity_score required for each recommendation tier.
    # Below the lowest threshold, the recommendation is AVOID.
    recommendation_thresholds: dict = field(
        default_factory=lambda: {
            "CRITICAL_BUY": 58,
            "STRONG_BUY": 46,
            "BUY": 34,
            "CONDITIONAL_BUY": 22,
            "WATCH": 13,
            "SKIP": 5,
        }
    )

    # Recommendation cannot reach a BUY tier below this confidence.
    min_confidence_for_buy: float = 35.0

    # Recommendation is forced to AVOID at or above this risk score.
    max_risk_before_avoid: float = 80.0

    # A rumored/unconfirmed opportunity can never be recommended above
    # this tier, regardless of score.
    rumor_recommendation_cap: str = "WATCH"

    # If resale evidence describes a complete set but the opportunity
    # itself is not the complete set, CRITICAL_BUY is blocked - this
    # is the highest tier still reachable.
    complete_set_mismatch_recommendation_cap: str = "STRONG_BUY"

    # Recommended quantity never exceeds this, no matter how strong
    # the opportunity looks.
    max_recommended_quantity: int = 3

    recommendation_base_quantity: dict = field(
        default_factory=lambda: {
            "CRITICAL_BUY": 3,
            "STRONG_BUY": 2,
            "BUY": 2,
            "CONDITIONAL_BUY": 1,
            "WATCH": 0,
            "SKIP": 0,
            "AVOID": 0,
        }
    )

    # Acquisition-score capital-locked-per-unit thresholds.
    high_spend_threshold: float = 100.0
    very_high_spend_threshold: float = 500.0

    # Scarcity-score stated-quantity thresholds.
    low_stated_quantity_threshold: int = 100
    moderate_stated_quantity_threshold: int = 500
    high_stated_quantity_threshold: int = 2000
