"""
Atlas v21 - Module 3: optional category/franchise benchmark lookups.

Entirely optional context. The scoring engine must produce a complete
evaluation with none of this data - a missing benchmark stays unknown
rather than being assumed. There are no built-in per-brand strength
values here on purpose: inventing "Pokemon is strong, Brand X is weak"
would violate the mission's evidence-based mandate. Callers supply
their own benchmarks (from real market history) via ScoringContext.
"""

from dataclasses import dataclass


@dataclass
class CategoryBenchmark:
    category: str
    typical_flip_spread_ratio: float | None = None
    typical_sales_velocity: float | None = None
    notes: str | None = None


def get_category_benchmark(category, benchmarks=None):
    """
    Looks up a CategoryBenchmark from a caller-supplied benchmarks
    dict (category name -> CategoryBenchmark), case-insensitively.
    Returns None if no category or no matching benchmark is given -
    callers must not treat None as "poor category," only "unknown."
    """
    if not category or not benchmarks:
        return None

    return benchmarks.get(category.strip().lower())
