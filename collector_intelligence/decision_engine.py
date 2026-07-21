"""
Atlas v21 - Module 3: Collector Opportunity Scoring and Decision Engine.

Public entry point: evaluate_opportunity(opportunity, context=None,
config=None) -> OpportunityEvaluation. Never mutates the input
CollectorOpportunity; never invents evidence the opportunity doesn't
already carry (from Module 1 fields or Module 2's attached
`evidence`/`risks`/`catalyst_signals`).
"""

from collector_intelligence import scoring
from collector_intelligence.scoring_config import ScoringConfig
from collector_intelligence.scoring_models import OpportunityEvaluation


RECOMMENDATION_ORDER = [
    "CRITICAL_BUY",
    "STRONG_BUY",
    "BUY",
    "CONDITIONAL_BUY",
    "WATCH",
    "SKIP",
    "AVOID",
]

BUY_TIERS = {"CRITICAL_BUY", "STRONG_BUY", "BUY", "CONDITIONAL_BUY"}

FLIP_TIME_HORIZONS = {
    "FLIP_NOW": "days",
    "QUICK_FLIP": "1-3 weeks",
}

HOLD_TIME_HORIZONS = {
    "HOLD_SHORT": "1-3 months",
    "HOLD_MEDIUM": "3-9 months",
    "HOLD_LONG": "9+ months",
}


def _cap_recommendation(current, cap):
    """Returns whichever of `current`/`cap` is worse (never upgrades)."""
    if RECOMMENDATION_ORDER.index(current) < RECOMMENDATION_ORDER.index(cap):
        return cap

    return current


def compute_opportunity_score(scores, risk_score, confidence_score, config):
    """
    Weighted sum of component scores, then risk subtracts from it, then
    confidence caps it. Deliberately not a simple average - risk
    reduces opportunity quality and low confidence caps the ceiling.
    """
    base = sum(
        scores[name] * weight
        for name, weight in config.opportunity_weights.items()
    )

    risk_adjusted = base - (risk_score * config.risk_penalty_weight)

    ceiling = confidence_score + config.confidence_cap_margin
    capped = min(risk_adjusted, ceiling)

    return scoring.clamp(capped)


def _base_recommendation(opportunity_score, config):
    for tier in ["CRITICAL_BUY", "STRONG_BUY", "BUY", "CONDITIONAL_BUY", "WATCH", "SKIP"]:
        if opportunity_score >= config.recommendation_thresholds[tier]:
            return tier

    return "AVOID"


def _apply_recommendation_rules(
    opportunity_score,
    risk_score,
    confidence_score,
    rumored,
    complete_set_mismatch,
    config,
):
    recommendation = _base_recommendation(opportunity_score, config)
    blocking_reasons = []

    if rumored:
        capped = _cap_recommendation(
            recommendation, config.rumor_recommendation_cap
        )

        if capped != recommendation:
            blocking_reasons.append(
                "Rumored/unconfirmed release - capped at "
                f"{config.rumor_recommendation_cap}"
            )

        recommendation = capped

    if complete_set_mismatch:
        capped = _cap_recommendation(
            recommendation,
            config.complete_set_mismatch_recommendation_cap,
        )

        if capped != recommendation:
            blocking_reasons.append(
                "Resale evidence reflects a complete set, not this "
                "individual item - CRITICAL_BUY blocked"
            )

        recommendation = capped

    if (
        recommendation in BUY_TIERS
        and confidence_score < config.min_confidence_for_buy
    ):
        blocking_reasons.append(
            f"Confidence score {confidence_score:.0f} is below the "
            f"minimum of {config.min_confidence_for_buy:.0f} required "
            "for any buy recommendation"
        )
        recommendation = "WATCH"

    if risk_score >= config.max_risk_before_avoid:
        if recommendation != "AVOID":
            blocking_reasons.append(
                f"Risk score {risk_score:.0f} meets or exceeds the "
                f"maximum safe threshold of {config.max_risk_before_avoid:.0f}"
            )
        recommendation = "AVOID"

    return recommendation, blocking_reasons


def _choose_primary_strategy(scores, recommendation):
    if recommendation == "AVOID":
        return "AVOID"

    flip = scores["flip_score"]
    hold = scores["hold_score"]
    collector = scores["collector_score"]

    candidates = [
        ("FLIP_NOW", flip, flip >= 70),
        ("QUICK_FLIP", flip, flip >= 40),
        ("HOLD_LONG", hold, hold >= 70),
        ("HOLD_MEDIUM", hold, hold >= 50),
        ("HOLD_SHORT", hold, hold >= 30),
        ("COLLECT_ONLY", collector, collector >= 35),
    ]

    qualifying = [candidate for candidate in candidates if candidate[2]]

    if not qualifying:
        return "WATCH"

    best = max(qualifying, key=lambda candidate: candidate[1])
    return best[0]


def _recommended_quantity(recommendation, purchase_limit, config):
    base = config.recommendation_base_quantity.get(recommendation, 0)

    if base == 0:
        return 0

    quantity = min(base, config.max_recommended_quantity)

    if purchase_limit is not None:
        quantity = min(quantity, purchase_limit)

    return max(quantity, 0)


def _price_fields(opportunity, complete_set_mismatch):
    buy_price, buy_field = scoring.resolve_target_buy_price(opportunity)
    sell_price, sell_kind = scoring.resolve_target_sell_price(opportunity)

    estimated_profit = None
    estimated_roi_percent = None

    if buy_price is not None and sell_price is not None:
        estimated_profit = round(sell_price - buy_price, 2)

        if buy_price:
            estimated_roi_percent = round(
                (estimated_profit / buy_price) * 100, 2
            )

    warnings = []

    if complete_set_mismatch:
        warnings.append(
            "Estimated profit/ROI is based on a complete-set resale "
            "price applied to a single item - treat as optimistic"
        )

    return {
        "target_buy_price": buy_price,
        "target_sell_price": sell_price,
        "estimated_profit": estimated_profit,
        "estimated_roi_percent": estimated_roi_percent,
        "buy_field": buy_field,
        "sell_kind": sell_kind,
        "warnings": warnings,
    }


def _missing_information(opportunity, price_info):
    missing = []

    if price_info["target_buy_price"] is None:
        missing.append("required spend / retail price")

    if price_info["target_sell_price"] is None:
        missing.append("resale price evidence")

    if not opportunity.release_date:
        missing.append("release date")

    if not opportunity.status:
        missing.append("availability status")

    if opportunity.limited_quantity and opportunity.stated_quantity is None:
        missing.append("stated production quantity")

    if not opportunity.source_type:
        missing.append("source type")

    if not opportunity.franchise:
        missing.append("franchise")

    return missing


def _decision_summary(
    recommendation, primary_strategy, opportunity_score, blocking_reasons
):
    summary = (
        f"{recommendation} ({primary_strategy}) - opportunity score "
        f"{opportunity_score:.0f}/100."
    )

    if blocking_reasons:
        summary += " " + " ".join(blocking_reasons)

    return summary


def evaluate_opportunity(opportunity, context=None, config=None):
    """
    Evaluates a CollectorOpportunity and returns a complete, explainable
    OpportunityEvaluation. Deterministic and side-effect free - the
    input opportunity is never modified.
    """
    config = config or ScoringConfig()
    context = context

    rumored = scoring.is_rumored(opportunity)
    complete_set_mismatch = scoring.is_complete_set_mismatch(opportunity)

    collector_score, collector_explanation = scoring.score_collector(
        opportunity, context
    )
    flip_score, flip_explanation = scoring.score_flip(
        opportunity, context, complete_set_mismatch
    )
    hold_score, hold_explanation = scoring.score_hold(opportunity, context)
    scarcity_score, scarcity_explanation = scoring.score_scarcity(
        opportunity, context, config
    )
    demand_score, demand_explanation = scoring.score_demand(
        opportunity, context
    )
    hype_score, hype_explanation = scoring.score_hype(opportunity, context)
    acquisition_score, acquisition_explanation = scoring.score_acquisition(
        opportunity, context, config
    )
    risk_score, risk_explanation = scoring.score_risk(
        opportunity, context, complete_set_mismatch, rumored
    )
    confidence_score, confidence_explanation = scoring.score_confidence(
        opportunity, context, complete_set_mismatch, rumored
    )

    scores = {
        "collector_score": collector_score,
        "flip_score": flip_score,
        "hold_score": hold_score,
        "scarcity_score": scarcity_score,
        "demand_score": demand_score,
        "hype_score": hype_score,
        "acquisition_score": acquisition_score,
    }

    weighting_scores = dict(scores)
    weighting_scores["monetization_score"] = max(flip_score, hold_score)

    opportunity_score = compute_opportunity_score(
        weighting_scores, risk_score, confidence_score, config
    )

    recommendation, blocking_reasons = _apply_recommendation_rules(
        opportunity_score,
        risk_score,
        confidence_score,
        rumored,
        complete_set_mismatch,
        config,
    )

    primary_strategy = _choose_primary_strategy(scores, recommendation)

    recommended_quantity = _recommended_quantity(
        recommendation, opportunity.purchase_limit, config
    )

    price_info = _price_fields(opportunity, complete_set_mismatch)

    missing_information = _missing_information(opportunity, price_info)

    explanations = {
        "collector_score": collector_explanation,
        "flip_score": flip_explanation,
        "hold_score": hold_explanation,
        "scarcity_score": scarcity_explanation,
        "demand_score": demand_explanation,
        "hype_score": hype_explanation,
        "acquisition_score": acquisition_explanation,
        "risk_score": risk_explanation,
        "confidence_score": confidence_explanation,
    }

    positive_factors = []
    negative_factors = []
    warnings = list(price_info["warnings"])

    for name, explanation in explanations.items():
        for item in explanation["positives"]:
            if item not in positive_factors:
                positive_factors.append(item)

        for item in explanation["negatives"]:
            if item not in negative_factors:
                negative_factors.append(item)

    if complete_set_mismatch:
        warning = (
            "Resale evidence describes a complete set, not this "
            "individual item"
        )
        if warning not in warnings:
            warnings.append(warning)

    if rumored:
        warning = "This opportunity is rumored/unconfirmed"
        if warning not in warnings:
            warnings.append(warning)

    flip_time_horizon = FLIP_TIME_HORIZONS.get(primary_strategy)
    hold_time_horizon = HOLD_TIME_HORIZONS.get(primary_strategy)

    decision_summary = _decision_summary(
        recommendation, primary_strategy, opportunity_score, blocking_reasons
    )

    evaluation = OpportunityEvaluation(
        collector_score=collector_score,
        flip_score=flip_score,
        hold_score=hold_score,
        scarcity_score=scarcity_score,
        demand_score=demand_score,
        hype_score=hype_score,
        acquisition_score=acquisition_score,
        risk_score=risk_score,
        confidence_score=confidence_score,
        opportunity_score=opportunity_score,
        recommendation=recommendation,
        primary_strategy=primary_strategy,
        recommended_quantity=recommended_quantity,
        target_buy_price=price_info["target_buy_price"],
        target_sell_price=price_info["target_sell_price"],
        estimated_profit=price_info["estimated_profit"],
        estimated_roi_percent=price_info["estimated_roi_percent"],
        flip_time_horizon=flip_time_horizon,
        hold_time_horizon=hold_time_horizon,
        score_explanation=explanations,
        positive_factors=positive_factors,
        negative_factors=negative_factors,
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        missing_information=missing_information,
        decision_summary=decision_summary,
    )

    if context and context.overrides:
        for key, value in context.overrides.items():
            if hasattr(evaluation, key):
                setattr(evaluation, key, value)

    return evaluation
