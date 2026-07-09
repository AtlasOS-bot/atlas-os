import importlib

from brain.explanation_engine import explain
from decision.decision_engine import decide
from market.engine import MarketEngine
from reasoning.evidence import build_evidence
from reasoning.confidence import calculate_confidence
from reasoning.opportunity import calculate_opportunity
from reasoning.urgency import calculate_urgency
from reasoning.resale import estimate_resale


def reason(item, category="general"):
    category = category.lower().replace("-", "_").replace(" ", "_")

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

    watch_risk = any(e["type"] == "watch_risk" for e in evidence)

    decision = decide(
        score=score,
        reprint_risk=watch_risk,
        pattern_count=len(patterns),
    )

    confidence = calculate_confidence(evidence)
    opportunity = calculate_opportunity(score, confidence)
    urgency = calculate_urgency(item)
    market = MarketEngine.research(item)
    resale = estimate_resale(item)

    reasons = [e["reason"] for e in evidence]
    reasons.append(decision["reason"])

    result = {
        "score": score,
        "decision": decision["action"],
        "confidence": confidence,
        "opportunity": opportunity,
        "urgency": urgency,
        "market": market,
        "resale": resale,
        "evidence": evidence,
        "reasons": reasons,
        "competition_note": "Competition may be high, but Atlas treats high competition as context, not a score penalty.",
    }

    result["explanation"] = explain(item, result)

    return result


def calculate_score(evidence):
    base_score = 40
    evidence_score = sum(e.get("weight", 0) for e in evidence)

    return max(0, min(base_score + evidence_score, 100))


def load_knowledge(category):
    try:
        module = importlib.import_module(f"knowledge.{category}")
        attr = f"{category.upper()}_KNOWLEDGE"
        return getattr(module, attr, {})
    except Exception:
        return {}


def load_memory(category):
    try:
        module = importlib.import_module(f"memory.{category}_memory")
        func = getattr(module, f"{category}_memory")
        return func()
    except Exception:
        return {"total_items_seen": 0}


def load_patterns(category):
    try:
        module = importlib.import_module(f"patterns.{category}_patterns")
        func = getattr(module, "detect_patterns")
        return func()
    except Exception:
        return []


def load_rules(category):
    try:
        module = importlib.import_module(f"scouts.{category}.rules")
        attr = f"{category.upper()}_RULES"
        return getattr(module, attr, {})
    except Exception:
        return {}