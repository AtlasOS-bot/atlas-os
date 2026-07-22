"""
Atlas v21 - Module 7: catalog querying.

Every query returns results in deterministic (sorted-by-ID) order.
"""


class UnknownScoutError(KeyError):
    pass


class UnknownSourceError(KeyError):
    pass


def get_scout(catalog, scout_id):
    scout = catalog.scouts.get(scout_id)
    if scout is None:
        raise UnknownScoutError(f"No scout with id {scout_id!r}.")
    return scout


def get_source(catalog, source_id):
    source = catalog.sources.get(source_id)
    if source is None:
        raise UnknownSourceError(f"No source with id {source_id!r}.")
    return source


def _matches(value, allowed):
    if allowed is None:
        return True
    if isinstance(allowed, (list, tuple, set, frozenset)):
        return value in allowed
    return value == allowed


def _matches_any(values, allowed):
    if allowed is None:
        return True
    allowed_set = set(allowed) if isinstance(allowed, (list, tuple, set, frozenset)) else {allowed}
    return bool(set(values or []) & allowed_set)


def list_scouts(catalog, filters=None):
    filters = filters or {}
    results = []

    for scout in catalog.scouts.values():
        if not _matches(scout.enabled, filters.get("enabled")):
            continue
        if not _matches(scout.priority, filters.get("priority")):
            continue
        if not _matches_any(scout.categories, filters.get("category")):
            continue
        if not _matches_any(scout.brands, filters.get("brand")):
            continue
        if not _matches_any(scout.tags, filters.get("tags")):
            continue
        results.append(scout)

    return sorted(results, key=lambda s: s.scout_id)


def list_sources(catalog, filters=None, now=None):
    filters = filters or {}
    results = []

    for source in catalog.sources.values():
        if not _matches(source.enabled, filters.get("enabled")):
            continue
        if not _matches(source.source_type, filters.get("source_type")):
            continue
        if not _matches(source.connector_type, filters.get("connector")):
            continue
        if not _matches(source.authority_level, filters.get("authority")):
            continue
        if not _matches(source.lifecycle_state, filters.get("lifecycle")):
            continue
        if not _matches(source.region, filters.get("region")):
            continue
        if not _matches(source.language, filters.get("language")):
            continue
        if not _matches_any(source.tags, filters.get("tags")):
            continue
        if not _matches_any(source.category_ids, filters.get("category")):
            continue
        if not _matches(source.brand_id, filters.get("brand")):
            continue
        if not _matches_any(source.scout_ids, filters.get("scout")):
            continue

        if "due" in filters:
            from collector_intelligence.catalog_planning import is_source_due
            due, _ = is_source_due(catalog, source, now=now)
            if due != filters["due"]:
                continue

        results.append(source)

    return sorted(results, key=lambda s: s.source_id)
