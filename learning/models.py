from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LearningRecord:
    record_id: str
    recorded_at: str

    category: str
    brand: str
    title: str
    official_url: str | None

    decision: str
    score: float
    confidence: str
    opportunity: str
    urgency: str

    retail_price: float | None
    average_market_price: float | None
    estimated_profit: float | None
    estimated_roi: float | None

    pattern_score: float
    pattern_confidence: str
    pattern_names: list[str] = field(default_factory=list)

    evidence_types: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)