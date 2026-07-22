"""
Atlas v21 - Module 4: data models for aggregation and finalization.

Every model here is a plain dataclass with a to_dict() that only
returns JSON-compatible primitives, lists, and dicts - no raw source
objects or Module 2/3 dataclasses are embedded directly, so a
FinalizedCollectorOpportunity can always be serialized safely.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvidenceRecord:
    field_name: str
    proposed_value: Any

    normalized_value: Any = None

    source_name: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    source_published_at: str | None = None

    evidence_text: str = ""
    confidence: float = 0.0

    confirmed: bool = False
    estimated: bool = False
    rumored: bool = False

    accepted: bool = False
    rejection_reason: str | None = None

    unit_scope: str | None = None
    observed_at: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class FieldConflict:
    field_name: str
    competing_values: list[Any] = field(default_factory=list)
    evidence_references: list[str] = field(default_factory=list)
    severity: str = "LOW"
    resolution: str = ""
    auto_resolved: bool = True
    requires_manual_review: bool = False
    explanation: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class OpportunityChange:
    field_name: str
    previous_value: Any
    new_value: Any
    reason: str
    supporting_source: str | None = None
    confidence_change: float | None = None
    material_change: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class SourceDisposition:
    source_title: str
    source_name: str | None
    source_type: str | None
    source_url: str | None
    disposition: str
    reason: str

    def to_dict(self):
        return asdict(self)


@dataclass
class MergeDecision:
    field_name: str
    chosen_value: Any
    chosen_source: str | None
    rule_applied: str
    alternative_values: list[Any] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class FinalizedCollectorOpportunity:
    opportunity: Any  # CollectorOpportunity
    evaluation: Any  # OpportunityEvaluation

    source_results: list[SourceDisposition] = field(default_factory=list)
    accepted_sources: list[SourceDisposition] = field(default_factory=list)
    rejected_sources: list[SourceDisposition] = field(default_factory=list)
    merged_source_count: int = 0

    evidence_ledger: list[EvidenceRecord] = field(default_factory=list)
    merge_decisions: list[MergeDecision] = field(default_factory=list)
    conflicts: list[FieldConflict] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)

    identity_confidence: float = 0.0
    market_confidence: float = 0.0
    finalization_confidence: float = 0.0

    change_summary: list[OpportunityChange] = field(default_factory=list)
    previous_dedup_key: str | None = None
    current_dedup_key: str | None = None

    requires_manual_review: bool = False
    manual_review_reasons: list[str] = field(default_factory=list)

    finalized_at: str = ""

    def to_dict(self):
        return {
            "opportunity": self.opportunity.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "source_results": [s.to_dict() for s in self.source_results],
            "accepted_sources": [s.to_dict() for s in self.accepted_sources],
            "rejected_sources": [s.to_dict() for s in self.rejected_sources],
            "merged_source_count": self.merged_source_count,
            "evidence_ledger": [e.to_dict() for e in self.evidence_ledger],
            "merge_decisions": [d.to_dict() for d in self.merge_decisions],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "warnings": self.warnings,
            "missing_information": self.missing_information,
            "identity_confidence": self.identity_confidence,
            "market_confidence": self.market_confidence,
            "finalization_confidence": self.finalization_confidence,
            "change_summary": [c.to_dict() for c in self.change_summary],
            "previous_dedup_key": self.previous_dedup_key,
            "current_dedup_key": self.current_dedup_key,
            "requires_manual_review": self.requires_manual_review,
            "manual_review_reasons": self.manual_review_reasons,
            "finalized_at": self.finalized_at,
        }


@dataclass
class ManualReviewGroup:
    source_titles: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class FinalizationBatchResult:
    finalized_opportunities: list[FinalizedCollectorOpportunity] = field(
        default_factory=list
    )
    ungrouped_sources: list[SourceDisposition] = field(default_factory=list)
    rejected_sources: list[SourceDisposition] = field(default_factory=list)
    manual_review_groups: list[ManualReviewGroup] = field(default_factory=list)

    total_sources: int = 0
    accepted_source_count: int = 0
    rejected_source_count: int = 0
    group_count: int = 0

    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "finalized_opportunities": [
                f.to_dict() for f in self.finalized_opportunities
            ],
            "ungrouped_sources": [s.to_dict() for s in self.ungrouped_sources],
            "rejected_sources": [s.to_dict() for s in self.rejected_sources],
            "manual_review_groups": [
                g.to_dict() for g in self.manual_review_groups
            ],
            "total_sources": self.total_sources,
            "accepted_source_count": self.accepted_source_count,
            "rejected_source_count": self.rejected_source_count,
            "group_count": self.group_count,
            "warnings": self.warnings,
        }
