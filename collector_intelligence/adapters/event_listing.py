"""
EventListingAdapter - convention/event announcements: venue, dates,
registration, exclusives, attendance requirements.
"""

from collector_intelligence.adapter_base import SourceAdapter, record_transformation
from collector_intelligence.ingestion_fingerprinting import compute_fingerprint
from collector_intelligence.ingestion_normalization import (
    clean_text,
    normalize_source_name,
    normalize_timestamp,
    normalize_url,
)
from collector_intelligence.ingestion_validation import (
    validate_event_dates,
    validate_non_empty_content,
    validate_timestamp,
    validate_url,
)


class EventListingAdapter(SourceAdapter):
    name = "event_listing"
    version = "1.0.0"
    supported_payload_types = (dict,)
    supported_source_types = ("EVENT",)

    def can_handle(self, payload):
        if not isinstance(payload, dict):
            return False
        return bool(
            payload.get("event_name")
            and (payload.get("event_start") or payload.get("event_url"))
        )

    def detection_confidence(self, payload):
        if not self.can_handle(payload):
            return 0.0, []

        present = [
            f for f in ("organizer", "venue", "event_start", "event_end", "region")
            if payload.get(f)
        ]
        confidence = min(0.6 + 0.07 * len(present), 0.93)
        return confidence, [
            f"Event-listing-shaped payload with fields: {', '.join(present) or 'event_name only'}"
        ]

    def validate(self, payload, config):
        errors = []
        warnings = []

        errors.extend(validate_non_empty_content(
            payload.get("event_name"), payload.get("announcement_text"),
            field_label="event_name/announcement_text",
        ))

        _, url_issues = validate_url(payload.get("event_url"), "event_url", config)
        errors.extend(i for i in url_issues if i.severity == "ERROR")
        warnings.extend(i for i in url_issues if i.severity == "WARNING")

        start_norm, start_issues = validate_timestamp(payload.get("event_start"), "event_start")
        warnings.extend(start_issues)

        end_norm, end_issues = validate_timestamp(payload.get("event_end"), "event_end")
        warnings.extend(end_issues)

        errors.extend(validate_event_dates(start_norm, end_norm))

        return errors, warnings

    def transform(self, payload, context, config):
        transformations = []

        event_name = clean_text(payload.get("event_name") or "")
        announcement = clean_text(payload.get("announcement_text") or "")

        lines = [f"Event:\n{event_name}"]

        if payload.get("organizer"):
            lines.append(f"Organizer:\n{clean_text(payload['organizer'])}")

        if payload.get("venue"):
            lines.append(f"Venue:\n{clean_text(payload['venue'])}")

        if payload.get("region"):
            lines.append(f"Region:\n{clean_text(payload['region'])}")

        if payload.get("event_start"):
            end_part = f" through {payload['event_end']}" if payload.get("event_end") else ""
            lines.append(f"Event dates:\n{payload['event_start']}{end_part}")

        if payload.get("registration_date"):
            lines.append(f"Registration date:\n{payload['registration_date']}")

        if payload.get("attendance_requirements"):
            lines.append(
                f"Attendance requirements:\n{clean_text(payload['attendance_requirements'])}"
            )

        if payload.get("exclusives"):
            exclusives = payload["exclusives"]
            text = ", ".join(exclusives) if isinstance(exclusives, list) else str(exclusives)
            lines.append(f"Event-exclusive items:\n{text}")

        if announcement:
            lines.append(f"Announcement:\n{announcement}")

        body = "\n\n".join(lines)

        transformations.append(record_transformation(
            "body", payload.get("announcement_text"), body, "structured_to_text",
            "Structured event fields converted into a deterministic, "
            "labeled text representation for Module 2.",
        ))

        fields = {
            "title": event_name,
            "body": body,
            "source_name": normalize_source_name(payload.get("organizer")) or event_name,
            "source_type": "EVENT",
            "source_url": normalize_url(payload.get("event_url"), config.supported_url_schemes)[0],
            "published_at": payload.get("event_start"),
        }

        return fields, transformations

    def extract_metadata(self, payload):
        return {
            "venue": payload.get("venue"),
            "region": payload.get("region"),
            "event_start": normalize_timestamp(payload.get("event_start"))[0],
            "event_end": normalize_timestamp(payload.get("event_end"))[0],
            "registration_date": payload.get("registration_date"),
            "attendance_requirements": payload.get("attendance_requirements"),
            "exclusives": payload.get("exclusives"),
        }

    def fingerprint(self, payload):
        return compute_fingerprint(
            canonical_url=payload.get("event_url"),
            title=payload.get("event_name"),
            content=payload.get("announcement_text"),
            source_name=payload.get("organizer"),
            published_at=payload.get("event_start"),
        )
