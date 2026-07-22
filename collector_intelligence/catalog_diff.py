"""
Atlas v21 - Module 7: catalog diffing.
"""

from collector_intelligence.catalog_models import CatalogDiff


_SOURCE_TRACKED_FIELDS = (
    "url", "enabled", "lifecycle_state", "connector_type", "source_type",
    "authority_level", "brand_id", "scout_ids", "schedule", "connector_config",
    "expected_evidence", "health_policy",
)


def _source_field_value(source, field_name):
    value = getattr(source, field_name)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return sorted(value)
    return value


def diff_catalogs(old_catalog, new_catalog):
    diff = CatalogDiff()

    old_sources = old_catalog.sources
    new_sources = new_catalog.sources

    added_ids = sorted(set(new_sources) - set(old_sources))
    removed_ids = sorted(set(old_sources) - set(new_sources))
    common_ids = sorted(set(old_sources) & set(new_sources))

    diff.added_sources = added_ids
    diff.removed_sources = removed_ids

    for source_id in common_ids:
        old_source = old_sources[source_id]
        new_source = new_sources[source_id]

        changed_fields = []
        for field_name in _SOURCE_TRACKED_FIELDS:
            old_value = _source_field_value(old_source, field_name)
            new_value = _source_field_value(new_source, field_name)
            if old_value != new_value:
                changed_fields.append(field_name)

        if changed_fields:
            diff.changed_sources.append({
                "source_id": source_id, "changed_fields": changed_fields,
            })

        if old_source.enabled != new_source.enabled:
            (diff.enabled_sources if new_source.enabled else diff.disabled_sources).append(source_id)

        if "schedule" in changed_fields:
            diff.changed_schedules.append({
                "source_id": source_id,
                "old": old_source.schedule.to_dict(), "new": new_source.schedule.to_dict(),
            })

        if "connector_config" in changed_fields:
            diff.changed_connector_configs.append({
                "source_id": source_id,
                "old": old_source.connector_config, "new": new_source.connector_config,
            })

        if "scout_ids" in changed_fields:
            diff.changed_scouts.append({
                "source_id": source_id,
                "old": sorted(old_source.scout_ids), "new": sorted(new_source.scout_ids),
            })

        # --- breaking-change classification ---

        if old_source.url and new_source.url and old_source.url != new_source.url:
            diff.breaking_changes.append(
                f"source {source_id!r} kept its ID but its canonical URL changed "
                f"from {old_source.url!r} to {new_source.url!r} - verify this is "
                f"the same real-world source, not a reused ID."
            )

        if (
            old_source.connector_type and new_source.connector_type
            and old_source.connector_type != new_source.connector_type
        ):
            diff.breaking_changes.append(
                f"source {source_id!r} connector changed from "
                f"{old_source.connector_type!r} to {new_source.connector_type!r}."
            )

        if old_source.source_type != new_source.source_type:
            diff.breaking_changes.append(
                f"source {source_id!r} source_type changed from "
                f"{old_source.source_type!r} to {new_source.source_type!r}."
            )

        from collector_intelligence.catalog_models import AUTHORITY_RANK
        if (
            old_source.authority_level in AUTHORITY_RANK
            and new_source.authority_level in AUTHORITY_RANK
            and old_source.authority_level.startswith("official")
            and not new_source.authority_level.startswith("official")
        ):
            diff.breaking_changes.append(
                f"source {source_id!r} was downgraded from official authority "
                f"({old_source.authority_level!r}) to {new_source.authority_level!r}."
            )

    for source_id in removed_ids:
        old_source = old_sources[source_id]
        if old_source.enabled and old_source.lifecycle_state == "active":
            diff.breaking_changes.append(
                f"active source {source_id!r} was removed entirely."
            )

    for brand_id in sorted(set(old_catalog.brands) | set(new_catalog.brands)):
        old_brand = old_catalog.brands.get(brand_id)
        new_brand = new_catalog.brands.get(brand_id)
        if old_brand is None or new_brand is None or old_brand.to_dict() != new_brand.to_dict():
            diff.changed_brands.append({"brand_id": brand_id})

    for scout_id in sorted(set(old_catalog.scouts) | set(new_catalog.scouts)):
        old_scout = old_catalog.scouts.get(scout_id)
        new_scout = new_catalog.scouts.get(scout_id)

        if new_scout and new_scout.enabled:
            runnable = [
                sid for sid in new_scout.source_ids
                if sid in new_sources and new_sources[sid].enabled
                and new_sources[sid].lifecycle_state in ("active", "proposed")
            ]
            if not runnable:
                diff.breaking_changes.append(
                    f"scout {scout_id!r} has zero runnable sources after this change."
                )

        if old_scout is None or new_scout is None:
            continue
        if sorted(old_scout.source_ids) != sorted(new_scout.source_ids):
            diff.changed_scouts.append({"scout_id": scout_id, "reason": "source_ids changed"})

    return diff
