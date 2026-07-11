from patterns.history import PATTERN_HISTORY


class PatternMatcher:

    @staticmethod
    def find_matches(item):
        title = (item.get("title") or "").lower()
        description = (item.get("description") or "").lower()
        category = (item.get("category") or "").lower()

        searchable_text = f"{title} {description}"
        matches = []

        for pattern_name, pattern in PATTERN_HISTORY.items():
            keywords = [
                keyword.lower()
                for keyword in pattern.get("keywords", [])
            ]

            matched_keywords = [
                keyword
                for keyword in keywords
                if keyword in searchable_text
            ]

            category_matches = (
                bool(category)
                and pattern.get("category", "").lower() == category
            )

            if not matched_keywords and not category_matches:
                continue

            match_strength = len(matched_keywords)

            if category_matches:
                match_strength += 1

            matches.append({
                "name": pattern_name,
                "pattern": pattern,
                "matched_keywords": matched_keywords,
                "category_match": category_matches,
                "match_strength": match_strength,
            })

        return matches