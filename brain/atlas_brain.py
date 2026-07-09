from brain.explanation_engine import explain
from knowledge.pokemon import POKEMON_KNOWLEDGE
from memory.pokemon_memory import pokemon_memory
from patterns.pokemon_patterns import detect_patterns
from decision.decision_engine import decide


class AtlasBrain:
    @staticmethod
    def analyze(item, category="pokemon"):
        if category == "pokemon":
            return AtlasBrain._analyze_pokemon(item)

        return AtlasBrain._fallback(item, category)

    @staticmethod
    def _fallback(item, category):
        result = {
            "score": 40,
            "decision": "WATCH",
            "confidence": "LOW",
            "reasons": [
                f"Atlas Brain does not fully support {category} analysis yet."
            ],
            "competition_note": "Competition is context, not a score penalty.",
        }

        result["explanation"] = explain(item, result)
        return result

    @staticmethod
    def _analyze_pokemon(item):
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()

        score = 40
        reasons = []

        priority_terms = [
            "pokemon center",
            "pokémon center",
            "exclusive",
            "elite trainer box",
            "etb",
            "booster bundle",
            "promo",
            "special collection",
            "limited",
        ]

        watch_terms = [
            "reprint",
            "restock",
            "available again",
        ]

        memory = pokemon_memory()
        patterns = detect_patterns()

        for term in priority_terms:
            if term in text:
                score += 8
                knowledge = POKEMON_KNOWLEDGE.get(term)

                if knowledge:
                    reasons.append(knowledge["reason"])
                else:
                    reasons.append(f"Atlas detected a Pokémon priority signal: {term}.")

        reprint_risk = any(term in text for term in watch_terms)

        if reprint_risk:
            reasons.append(POKEMON_KNOWLEDGE["reprint"]["reason"])
            reasons.append(POKEMON_KNOWLEDGE["reprint"]["risk"])

        if memory["total_items_seen"] > 0:
            reasons.append(
                f"Atlas memory: {memory['total_items_seen']} Pokémon opportunities have already been observed."
            )

        for pattern in patterns:
            reasons.append(f"Pattern detected: {pattern}")

        if "pokemon center" in text or "pokémon center" in text:
            reasons.append(
                "Pokémon Center source increases confidence because products mentioned there may receive collector attention quickly."
            )

        if "exclusive" in text:
            reasons.append(POKEMON_KNOWLEDGE["exclusive"]["reason"])
            reasons.append(POKEMON_KNOWLEDGE["exclusive"]["risk"])

        score = max(0, min(score, 100))

        decision = decide(
            score=score,
            reprint_risk=reprint_risk,
            pattern_count=len(patterns),
        )

        reasons.append(decision["reason"])

        result = {
            "score": score,
            "decision": decision["action"],
            "confidence": decision["confidence"],
            "reasons": reasons,
            "competition_note": "Competition may be high, but Atlas treats high competition as context, not a score penalty.",
        }

        result["explanation"] = explain(item, result)
        return result