import importlib

from brain.explanation_engine import explain
from decision.decision_engine import decide
from market.engine import MarketEngine
from market.roi import ROIEngine
from reasoning.confidence import calculate_confidence
from reasoning.evidence import build_evidence
from reasoning.opportunity import calculate_opportunity
from reasoning.resale import estimate_resale
from reasoning.urgency import calculate_urgency


def reason(item, category="general"):
    category = normalize_category(category)

    knowledge = load_knowledge(category)
    memory = load_memory(category)
    patterns = load_patterns(category)
    rules = load_rules(category)

    evidence = build_evidence(
        item=item,
        knowledge=knowledge,
        rules=rules,
        memory=memory,
        patterns=patterns,
    )

    score = calculate_score(evidence)

    watch_risk = any(
        evidence_item.get("type") in {
            "watch_risk",
            "restock",
            "reprint",
        }
        for evidence_item in evidence
    )

    confidence = calculate_confidence(evidence)
    opportunity = calculate_opportunity(score, confidence)
    urgency = calculate_urgency(item)

    market = MarketEngine.research(item)
    market_summary = market.get("summary", {})

    retail_price = item.get("retail_price")
    average_sold_price = market_summary.get("average_price")

    roi = ROIEngine.calculate(
        retail_price=retail_price,
        average_sold_price=average_sold_price,
        shipping_cost=item.get("shipping_cost"),
        fee_rate=item.get("fee_rate"),
    )

    decision = decide(
        score=score,
        reprint_risk=watch_risk,
        pattern_count=len(patterns),
        roi=roi,
    )

    resale = estimate_resale(item)

    reasons = [
        evidence_item["reason"]
        for evidence_item in evidence
    ]

    if roi is not None:
        reasons.append(
            f"Estimated profit is ${roi['profit']:.2f} with an "
            f"estimated ROI of {roi['roi']:.2f}%."
        )
    else:
        reasons.append(
            "Atlas does not yet have both retail price and market-price "
            "data, so ROI could not be calculated."
        )

    reasons.append(decision["reason"])

    result = {
        "score": score,
        "decision": decision["action"],
        "confidence": decision["confidence"],
        "signal_confidence": confidence,
        "opportunity": opportunity,
        "urgency": urgency,
        "market": market,
        "roi": roi,
        "resale": resale,
        "evidence": evidence,
        "reasons": reasons,
        "competition_note": (
            "Competition may be high, but Atlas treats high competition "
            "as context, not a score penalty."
        ),
    }

    result["explanation"] = explain(item, result)

    return result


def normalize_category(category):
    return (
        (category or "general")
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def calculate_score(evidence):
    base_score = 40

    evidence_score = sum(
        evidence_item.get("weight", 0)
        for evidence_item in evidence
    )

    return max(
        0,
        min(base_score + evidence_score, 100),
    )


def load_knowledge(category):
    try:
        module = importlib.import_module(
            f"knowledge.{category}"
        )
        attribute = f"{category.upper()}_KNOWLEDGE"
        return getattr(module, attribute, {})
    except (ImportError, AttributeError):
        return {}


def load_memory(category):
    try:
        module = importlib.import_module(
            f"memory.{category}_memory"
        )
        function = getattr(
            module,
            f"{category}_memory",
        )
        return function()
    except (ImportError, AttributeError):
        return {
            "total_items_seen": 0,
        }


def load_patterns(category):
    try:
        module = importlib.import_module(
            f"patterns.{category}_patterns"
        )
        function = getattr(
            module,
            "detect_patterns",
        )
        return function()
    except (ImportError, AttributeError):
        return []


def load_rules(category):
    try:
        module = importlib.import_module(
            f"scouts.{category}.rules"
        )
        attribute = f"{category.upper()}_RULES"
        return getattr(module, attribute, {})
    except (ImportError, AttributeError):
        return {}