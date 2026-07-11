import importlib

from brain.explanation_engine import explain
from decision.decision_engine import decide
from market.engine import MarketEngine
from market.roi import ROIEngine
from patterns.engine import PatternEngine
from popularity.engine import PopularityEngine
from reasoning.confidence import calculate_confidence
from reasoning.evidence import build_evidence
from reasoning.opportunity import calculate_opportunity
from reasoning.resale import estimate_resale
from reasoning.urgency import calculate_urgency


def reason(item, category="general"):
    category = normalize_category(category)

    knowledge = load_knowledge(category)
    memory = load_memory(category)
    legacy_patterns = load_patterns(category)
    rules = load_rules(category)

    pattern_analysis = PatternEngine.analyze(
        item
    )

    pattern_matches = pattern_analysis.get(
        "matches",
        [],
    )

    pattern_summary = pattern_analysis.get(
        "summary",
        {},
    )

    popularity = PopularityEngine.analyze(
        item=item,
        category=category,
    )

    evidence = build_evidence(
        item=item,
        knowledge=knowledge,
        rules=rules,
        memory=memory,
        patterns=legacy_patterns,
    )

    if pattern_matches:
        evidence.append({
            "type": "historical_pattern_match",
            "signal": "historical_pattern_match",
            "weight": pattern_evidence_weight(
                pattern_summary
            ),
            "reason": build_pattern_reason(
                pattern_analysis
            ),
        })

    popularity_weight = popularity_evidence_weight(
        popularity
    )

    if popularity_weight != 0:
        evidence.append({
            "type": "popularity",
            "signal": "popularity",
            "weight": popularity_weight,
            "reason": (
                f"Popularity score: {popularity['score']}/100 "
                f"({popularity['level']}); confidence: "
                f"{popularity['confidence']}."
            ),
        })

    score = calculate_score(evidence)

    watch_risk = any(
        evidence_item.get("type") in {
            "watch_risk",
            "restock",
            "reprint",
        }
        for evidence_item in evidence
    )

    signal_confidence = calculate_confidence(
        evidence
    )

    opportunity = calculate_opportunity(
        score,
        signal_confidence,
    )

    urgency = calculate_urgency(
        item
    )

    market = MarketEngine.research(
        item
    )

    market_summary = market.get(
        "summary",
        {},
    )

    retail_price = item.get(
        "retail_price"
    )

    average_sold_price = (
        market_summary.get(
            "average_price"
        )
    )

    roi = ROIEngine.calculate(
        retail_price=retail_price,
        average_sold_price=average_sold_price,
        shipping_cost=item.get(
            "shipping_cost"
        ),
        fee_rate=item.get(
            "fee_rate"
        ),
    )

    decision = decide(
        score=score,
        reprint_risk=watch_risk,
        pattern_count=len(
            pattern_matches
        ),
        roi=roi,
    )

    resale = estimate_resale(
        item
    )

    reasons = [
        evidence_item["reason"]
        for evidence_item in evidence
    ]

    reasons.extend(
        popularity.get(
            "reasons",
            [],
        )
    )

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

    reasons.append(
        decision["reason"]
    )

    result = {
        "score": score,
        "decision": decision["action"],
        "confidence": decision["confidence"],
        "signal_confidence": signal_confidence,
        "opportunity": opportunity,
        "urgency": urgency,
        "popularity": popularity,
        "market": market,
        "roi": roi,
        "resale": resale,
        "patterns": pattern_analysis,
        "evidence": evidence,
        "reasons": reasons,
        "competition_note": (
            "Competition may be high, but Atlas treats high competition "
            "as context, not a score penalty."
        ),
    }

    result["explanation"] = explain(
        item,
        result,
    )

    return result


def popularity_evidence_weight(
    popularity,
):
    score = popularity.get(
        "score",
        0,
    )

    if score >= 85:
        return 18

    if score >= 70:
        return 14

    if score >= 55:
        return 10

    if score >= 35:
        return 5

    if score <= 15:
        return -3

    return 0


def pattern_evidence_weight(
    pattern_summary,
):
    confidence = pattern_summary.get(
        "confidence",
        "LOW",
    )

    weights = {
        "VERY HIGH": 12,
        "HIGH": 9,
        "MEDIUM": 6,
        "LOW": 3,
    }

    return weights.get(
        confidence,
        3,
    )


def build_pattern_reason(
    pattern_analysis,
):
    summary = pattern_analysis.get(
        "summary",
        {},
    )

    matches = pattern_analysis.get(
        "matches",
        [],
    )

    names = [
        match.get(
            "name",
            "unknown pattern",
        )
        for match in matches[:3]
    ]

    pattern_names = ", ".join(
        names
    )

    return (
        f"Atlas matched {len(matches)} historical pattern(s): "
        f"{pattern_names}. Historical pattern score: "
        f"{summary.get('pattern_score', 0):.2f}; "
        f"confidence: {summary.get('confidence', 'LOW')}."
    )


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
        evidence_item.get(
            "weight",
            0,
        )
        for evidence_item in evidence
    )

    return max(
        0,
        min(
            base_score + evidence_score,
            100,
        ),
    )


def load_knowledge(category):
    try:
        module = importlib.import_module(
            f"knowledge.{category}"
        )

        attribute = (
            f"{category.upper()}_KNOWLEDGE"
        )

        return getattr(
            module,
            attribute,
            {},
        )

    except (
        ImportError,
        AttributeError,
    ):
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

    except (
        ImportError,
        AttributeError,
    ):
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

    except (
        ImportError,
        AttributeError,
    ):
        return []


def load_rules(category):
    try:
        module = importlib.import_module(
            f"scouts.{category}.rules"
        )

        attribute = (
            f"{category.upper()}_RULES"
        )

        return getattr(
            module,
            attribute,
            {},
        )

    except (
        ImportError,
        AttributeError,
    ):
        return {}