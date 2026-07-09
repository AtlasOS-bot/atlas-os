from signals.engine import SignalEngine


def build_evidence(item, knowledge, rules, memory, patterns):

    item = dict(item)
    item["patterns"] = patterns

    evidence = SignalEngine.evaluate(item)

    if memory.get("total_items_seen", 0) > 0:

        evidence.append({
            "type": "memory",
            "signal": "memory",
            "weight": 5,
            "reason": f"Atlas has already seen {memory['total_items_seen']} similar opportunities.",
        })

    if not evidence:

        evidence.append({
            "type": "baseline",
            "signal": "baseline",
            "weight": 0,
            "reason": "No meaningful evidence detected.",
        })

    return evidence