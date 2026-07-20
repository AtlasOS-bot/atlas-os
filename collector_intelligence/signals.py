"""
Signal types and detection result models for Module 2. This module
only defines structure - detection logic lives in extraction.py and
detector.py.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SignalType(str, Enum):
    COLLABORATION = "COLLABORATION"
    ANNIVERSARY = "ANNIVERSARY"
    EXCLUSIVE_PROMO = "EXCLUSIVE_PROMO"
    SPEND_REQUIREMENT = "SPEND_REQUIREMENT"
    RETAIL_PRICE = "RETAIL_PRICE"
    OBSERVED_RESALE_PRICE = "OBSERVED_RESALE_PRICE"
    PURCHASE_LIMIT = "PURCHASE_LIMIT"
    LIMITED_QUANTITY = "LIMITED_QUANTITY"
    NUMBERED_RELEASE = "NUMBERED_RELEASE"
    FIRST_EDITION = "FIRST_EDITION"
    FIRST_COLLABORATION = "FIRST_COLLABORATION"
    EXCLUSIVE_ARTWORK = "EXCLUSIVE_ARTWORK"
    EXCLUSIVE_CHARACTER = "EXCLUSIVE_CHARACTER"
    EVENT_EXCLUSIVE = "EVENT_EXCLUSIVE"
    CONVENTION_EXCLUSIVE = "CONVENTION_EXCLUSIVE"
    TOURNAMENT_EXCLUSIVE = "TOURNAMENT_EXCLUSIVE"
    RETAILER_EXCLUSIVE = "RETAILER_EXCLUSIVE"
    REGION_EXCLUSIVE = "REGION_EXCLUSIVE"
    MEMBERSHIP_EXCLUSIVE = "MEMBERSHIP_EXCLUSIVE"
    LOTTERY_REQUIRED = "LOTTERY_REQUIRED"
    EVENT_ATTENDANCE_REQUIRED = (
        "EVENT_ATTENDANCE_REQUIRED"
    )
    BUNDLE_REQUIRED = "BUNDLE_REQUIRED"
    REDEEMABLE_REWARD = "REDEEMABLE_REWARD"
    PURCHASE_WINDOW = "PURCHASE_WINDOW"
    RELEASE_DATE = "RELEASE_DATE"
    RELEASE_TIME = "RELEASE_TIME"
    STATUS_LIVE = "STATUS_LIVE"
    STATUS_SOLD_OUT = "STATUS_SOLD_OUT"
    STATUS_RESTOCKED = "STATUS_RESTOCKED"
    LOW_STOCK = "LOW_STOCK"
    RAPID_SELLOUT = "RAPID_SELLOUT"
    HIGH_DEMAND = "HIGH_DEMAND"
    RISING_DEMAND = "RISING_DEMAND"
    SURGING_DEMAND = "SURGING_DEMAND"
    HIGH_ACQUISITION_DIFFICULTY = (
        "HIGH_ACQUISITION_DIFFICULTY"
    )
    PROMOTIONAL_PACK = "PROMOTIONAL_PACK"
    SEALED_PRODUCT = "SEALED_PRODUCT"
    COMMUNITY_HYPE = "COMMUNITY_HYPE"
    RUMOR = "RUMOR"
    RISK_WARNING = "RISK_WARNING"


@dataclass
class SignalDetection:
    signal_type: str
    confidence: float

    evidence_text: str = ""
    evidence_start: int | None = None
    evidence_end: int | None = None

    extracted_value: Any = None
    extracted_unit: str | None = None

    confirmed: bool = False
    estimated: bool = False
    rumored: bool = False

    source_field: str | None = None
    notes: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ExtractedEntities:
    brand: str | None = None
    franchise: str | None = None
    collaboration_partner: str | None = None
    retailer: str | None = None
    event_name: str | None = None
    product_name: str | None = None
    character_names: list[str] = field(
        default_factory=list
    )
    artist_name: str | None = None
    region: str | None = None
    set_or_series: str | None = None

    def to_dict(self):
        return asdict(self)

    def has_any_identity(self):
        return any([
            self.brand,
            self.franchise,
            self.collaboration_partner,
            self.product_name,
        ])


@dataclass
class SignalDetectionResult:
    raw_source: Any
    detected_signals: list[SignalDetection] = (
        field(default_factory=list)
    )
    extracted_entities: ExtractedEntities = (
        field(
            default_factory=ExtractedEntities
        )
    )
    warnings: list[str] = field(
        default_factory=list
    )
    missing_critical_fields: list[str] = field(
        default_factory=list
    )
    overall_signal_confidence: float = 0.0
    collector_relevance_score: float = 0.0
    should_create_opportunity: bool = False
    rejection_reason: str | None = None

    def signals_of_type(self, signal_type):
        target = (
            signal_type.value
            if hasattr(signal_type, "value")
            else signal_type
        )

        return [
            signal
            for signal in self.detected_signals
            if signal.signal_type == target
        ]

    def has_signal(self, signal_type):
        return bool(
            self.signals_of_type(signal_type)
        )

    def to_dict(self):
        return {
            "detected_signals": [
                signal.to_dict()
                for signal in self.detected_signals
            ],
            "extracted_entities": (
                self.extracted_entities.to_dict()
            ),
            "warnings": self.warnings,
            "missing_critical_fields": (
                self.missing_critical_fields
            ),
            "overall_signal_confidence": (
                self.overall_signal_confidence
            ),
            "collector_relevance_score": (
                self.collector_relevance_score
            ),
            "should_create_opportunity": (
                self.should_create_opportunity
            ),
            "rejection_reason": (
                self.rejection_reason
            ),
        }
