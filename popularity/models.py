from dataclasses import asdict, dataclass, field


@dataclass
class PopularityResult:
    score: int
    level: str
    confidence: str
    source_count: int
    signals: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)