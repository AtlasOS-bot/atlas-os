from patterns.matcher import PatternMatcher
from patterns.scorer import PatternScorer


class PatternEngine:

    @staticmethod
    def analyze(item):
        matches = PatternMatcher.find_matches(item)
        summary = PatternScorer.score(matches)

        return {
            "matches": matches,
            "summary": summary,
        }