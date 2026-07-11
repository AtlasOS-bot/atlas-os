from datetime import datetime, timezone
from uuid import uuid4

from learning.models import LearningRecord
from learning.statistics import LearningStatistics
from learning.storage import JsonLearningStore


class LearningEngine:

    def __init__(self, store=None):
        self.store = store or JsonLearningStore()

    def record(self, item, analysis):
        record = self.build_record(
            item=item,
            analysis=analysis,
        )

        self.store.append(record)

        print(
            "Atlas learned:",
            record.title,
        )

        return record.to_dict()

    def summarize(self):
        records = self.store.all()

        return LearningStatistics.summarize(
            records
        )

    def summary_for(self, category, brand):
        group_key = f"{category}:{brand}"

        summaries = self.summarize()

        return summaries.get(
            group_key,
            {
                "total_records": 0,
                "records_with_roi": 0,
                "records_with_profit": 0,
                "average_roi": None,
                "average_profit": None,
                "average_market_price": None,
                "average_score": 0,
                "profitable_count": 0,
                "profitable_rate": None,
                "buy_count": 0,
                "strong_watch_count": 0,
                "watch_count": 0,
                "skip_count": 0,
                "buy_rate": 0,
                "confidence": "LOW",
            },
        )

    @staticmethod
    def build_record(item, analysis):
        roi = analysis.get("roi") or {}

        market = analysis.get("market") or {}
        market_summary = market.get("summary") or {}

        patterns = analysis.get("patterns") or {}
        pattern_summary = patterns.get("summary") or {}
        pattern_matches = patterns.get("matches") or []

        evidence = analysis.get("evidence") or []

        pattern_names = [
            match.get(
                "name",
                "unknown_pattern",
            )
            for match in pattern_matches
        ]

        evidence_types = [
            evidence_item.get(
                "type",
                "unknown",
            )
            for evidence_item in evidence
        ]

        return LearningRecord(
            record_id=str(uuid4()),
            recorded_at=datetime.now(
                timezone.utc
            ).isoformat(),

            category=(
                item.get("category")
                or "general"
            ),
            brand=(
                item.get("brand")
                or "Unknown"
            ),
            title=(
                item.get("title")
                or "Unknown item"
            ),
            official_url=item.get("url"),

            decision=analysis.get(
                "decision",
                "WATCH",
            ),
            score=analysis.get(
                "score",
                0,
            ),
            confidence=analysis.get(
                "confidence",
                "UNKNOWN",
            ),
            opportunity=analysis.get(
                "opportunity",
                "UNKNOWN",
            ),
            urgency=analysis.get(
                "urgency",
                "UNKNOWN",
            ),

            retail_price=item.get(
                "retail_price"
            ),
            average_market_price=market_summary.get(
                "average_price"
            ),
            estimated_profit=roi.get(
                "profit"
            ),
            estimated_roi=roi.get(
                "roi"
            ),

            pattern_score=pattern_summary.get(
                "pattern_score",
                0,
            ),
            pattern_confidence=pattern_summary.get(
                "confidence",
                "LOW",
            ),
            pattern_names=pattern_names,

            evidence_types=evidence_types,
            evidence=evidence,
        )