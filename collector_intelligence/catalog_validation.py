"""
Atlas v21 - Module 7: catalog validation.

Accepts either raw data (dict, straight off a JSON/YAML load) or an
already-built SourceCatalog, and produces a CatalogValidationResult
containing every problem found plus a best-effort normalized catalog
(built even when invalid, for tooling to inspect what's wrong).

Connector compatibility is checked against the REAL Module 6 connector
registry (never a hardcoded mirror of connector capabilities), per the
mission's explicit instruction not to duplicate connector behavior
here.
"""

from collector_intelligence.catalog_config import CatalogConfig
from collector_intelligence.catalog_models import (
    VALID_CONNECTOR_NAMES,
    BrandDefinition,
    CatalogValidationIssue,
    CatalogValidationResult,
    CategoryDefinition,
    ExpectedEvidenceDefinition,
    ScheduleSpec,
    ScoutDefinition,
    SourceCatalog,
    SourceDefinition,
    SourceHealthPolicy,
)
from collector_intelligence.catalog_normalization import (
    normalize_authority_level,
    normalize_catalog_source_type,
    normalize_catalog_url,
    normalize_connector_config_keys,
    normalize_connector_name,
    normalize_domain,
    normalize_id,
    normalize_language,
    normalize_lifecycle_state,
    normalize_priority,
    normalize_region,
    normalize_schedule_mode,
    normalize_tags,
    normalize_text_field,
)


CATALOG_SOURCE_TYPE_TO_DESCRIPTOR_TYPE = {
    "official_announcement": "announcement",
    "official_product_page": "retailer_page",
    "official_news": "announcement",
    "retailer_product_page": "retailer_page",
    "retailer_category_page": "html",
    "press_release": "announcement",
    "event_listing": "event_page",
    "convention_announcement": "event_page",
    "rss_feed": "rss",
    "atom_feed": "atom",
    "json_feed": "json",
    "xml_feed": "xml",
    "marketplace_export": "json",
    "marketplace_sold_data": "json",
    "marketplace_asking_data": "json",
    "community_post": "json",
    "social_post": "json",
    "manual_report": None,
}


def _err(path, code, message, recoverable=False, suggested_fix=None):
    return CatalogValidationIssue(
        path=path, error_code=code, message=message, severity="ERROR",
        recoverable=recoverable, suggested_fix=suggested_fix,
    )


def _warn(path, code, message, recoverable=True, suggested_fix=None):
    return CatalogValidationIssue(
        path=path, error_code=code, message=message, severity="WARNING",
        recoverable=recoverable, suggested_fix=suggested_fix,
    )


def _measure_depth(value, current=0):
    if current > 60:
        return current
    if isinstance(value, dict):
        return max((_measure_depth(v, current + 1) for v in value.values()), default=current)
    if isinstance(value, (list, tuple)):
        return max((_measure_depth(v, current + 1) for v in value), default=current)
    return current


def _is_json_compatible(value, depth=0):
    if depth > 20:
        return False
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_json_compatible(v, depth + 1) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(_is_json_compatible(v, depth + 1) for v in value)
    return False


def _scan_for_secrets(node, config, path="root"):
    issues = []
    patterns = config.compiled_secret_patterns()

    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"

            if key_text.lower().endswith("_ref"):
                # A symbolic reference (e.g. credential_ref: TARGET_API_TOKEN)
                # is exactly the allowed form - never flagged.
                continue

            if isinstance(value, str) and value.strip():
                if any(p.search(key_text) for p in patterns):
                    issues.append(_err(
                        child_path, "EMBEDDED_SECRET",
                        f"{child_path!r} looks like an embedded credential "
                        f"({key_text!r}). Store secrets symbolically, e.g. "
                        f"'{normalize_id(key_text)}_ref: SOME_ENV_VAR_NAME', "
                        f"never as a literal value.",
                        suggested_fix=f"Rename to '{key_text}_ref' and store only a symbolic name.",
                    ))

            issues.extend(_scan_for_secrets(value, config, child_path))

    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            issues.extend(_scan_for_secrets(item, config, f"{path}[{index}]"))

    return issues


def validate_catalog(catalog_or_data, config=None):
    config = config or CatalogConfig()

    if isinstance(catalog_or_data, SourceCatalog):
        raw = catalog_or_data.to_dict()
        raw["scouts"] = list(raw["scouts"].values())
        raw["brands"] = list(raw["brands"].values())
        raw["sources"] = list(raw["sources"].values())
        raw["categories"] = list(raw["categories"].values())
    else:
        raw = catalog_or_data

    errors = []
    warnings = []

    if not isinstance(raw, dict):
        errors.append(_err("root", "INVALID_ROOT_TYPE", "Catalog data must be a mapping/object."))
        return CatalogValidationResult(valid=False, errors=errors)

    depth = _measure_depth(raw)
    if depth > config.maximum_metadata_depth + 4:  # + headroom for the catalog's own structural nesting
        errors.append(_err(
            "root", "CATALOG_TOO_DEEP",
            f"Catalog nesting depth {depth} exceeds the configured safety limit.",
        ))

    errors.extend(_scan_for_secrets(raw, config))

    scouts_raw = raw.get("scouts") or []
    brands_raw = raw.get("brands") or []
    sources_raw = raw.get("sources") or []
    categories_raw = raw.get("categories") or []

    if len(sources_raw) > config.maximum_sources:
        errors.append(_err("sources", "TOO_MANY_SOURCES", f"{len(sources_raw)} sources exceeds the configured maximum of {config.maximum_sources}."))
    if len(scouts_raw) > config.maximum_scouts:
        errors.append(_err("scouts", "TOO_MANY_SCOUTS", f"{len(scouts_raw)} scouts exceeds the configured maximum of {config.maximum_scouts}."))

    categories = {}
    for index, entry in enumerate(categories_raw):
        category, entry_errors, entry_warnings = _build_category(entry, index, config)
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)
        if category:
            if category.category_id in categories:
                errors.append(_err(f"categories[{index}]", "DUPLICATE_CATEGORY_ID", f"Duplicate category_id {category.category_id!r}."))
            categories[category.category_id] = category

    for category_id, category in categories.items():
        if category.parent_category_id and category.parent_category_id not in categories:
            errors.append(_err(f"categories.{category_id}", "MISSING_CATEGORY_REFERENCE", f"parent_category_id {category.parent_category_id!r} does not exist."))

    cycle_issues = _detect_category_cycles(categories)
    errors.extend(cycle_issues)

    brands = {}
    for index, entry in enumerate(brands_raw):
        brand, entry_errors, entry_warnings = _build_brand(entry, index, config, categories)
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)
        if brand:
            if brand.brand_id in brands:
                errors.append(_err(f"brands[{index}]", "DUPLICATE_BRAND_ID", f"Duplicate brand_id {brand.brand_id!r}."))
            brands[brand.brand_id] = brand

    connector_registry = _load_connector_registry(config)

    sources = {}
    seen_urls = {}
    for index, entry in enumerate(sources_raw):
        source, entry_errors, entry_warnings = _build_source(
            entry, index, config, categories, brands, connector_registry,
        )
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)
        if source:
            if source.source_id in sources:
                errors.append(_err(f"sources[{index}]", "DUPLICATE_SOURCE_ID", f"Duplicate source_id {source.source_id!r}."))
            sources[source.source_id] = source

            if source.url:
                if source.url in seen_urls and not config.allow_duplicate_canonical_urls:
                    errors.append(_err(
                        f"sources.{source.source_id}", "DUPLICATE_CANONICAL_URL",
                        f"URL {source.url!r} is already used by source "
                        f"{seen_urls[source.url]!r}.",
                        suggested_fix="Set allow_duplicate_canonical_urls=True if this is intentional.",
                    ))
                else:
                    seen_urls[source.url] = source.source_id

    scouts = {}
    for index, entry in enumerate(scouts_raw):
        scout, entry_errors, entry_warnings = _build_scout(entry, index, config, categories, brands, sources)
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)
        if scout:
            if scout.scout_id in scouts:
                errors.append(_err(f"scouts[{index}]", "DUPLICATE_SCOUT_ID", f"Duplicate scout_id {scout.scout_id!r}."))
            scouts[scout.scout_id] = scout

    # Reconcile scout_ids <-> source.scout_ids in both directions so
    # ownership is always consistent regardless of which side declared it.
    for scout_id, scout in scouts.items():
        for source_id in scout.source_ids:
            source = sources.get(source_id)
            if source is None:
                errors.append(_err(f"scouts.{scout_id}.source_ids", "MISSING_SOURCE_REFERENCE", f"scout {scout_id!r} references unknown source_id {source_id!r}."))
            elif scout_id not in source.scout_ids:
                source.scout_ids.append(scout_id)

    for source_id, source in sources.items():
        for scout_id in source.scout_ids:
            scout = scouts.get(scout_id)
            if scout is None:
                errors.append(_err(f"sources.{source_id}.scout_ids", "MISSING_SCOUT_REFERENCE", f"source {source_id!r} references unknown scout_id {scout_id!r}."))
            elif source_id not in scout.source_ids:
                scout.source_ids.append(source_id)

    for scout_id, scout in scouts.items():
        if not scout.enabled:
            continue
        runnable = [
            sources[sid] for sid in scout.source_ids
            if sid in sources and sources[sid].lifecycle_state in ("active", "proposed")
        ]
        if not runnable:
            warnings.append(_warn(f"scouts.{scout_id}", "SCOUT_HAS_NO_RUNNABLE_SOURCE", f"Enabled scout {scout_id!r} has no enabled/proposed source."))

    for source_id, source in sources.items():
        if source.enabled and not source.scout_ids:
            warnings.append(_warn(f"sources.{source_id}", "SOURCE_HAS_NO_SCOUT", f"Enabled source {source_id!r} does not belong to any scout."))

        owning_scouts = [scouts.get(sid) for sid in source.scout_ids]
        if source.enabled and owning_scouts and all(s and not s.enabled for s in owning_scouts):
            warnings.append(_warn(f"sources.{source_id}", "SOURCE_SCOUT_STATE_CONFLICT", f"Source {source_id!r} is enabled but every owning scout is disabled."))

    if not isinstance(raw.get("metadata", {}), dict) or not _is_json_compatible(raw.get("metadata", {})):
        errors.append(_err("metadata", "METADATA_NOT_JSON_COMPATIBLE", "Top-level metadata must be JSON-compatible."))

    normalized_catalog = SourceCatalog(
        catalog_version=str(raw.get("catalog_version", "1.0.0")),
        schema_version=str(raw.get("schema_version", "1.0.0")),
        generated_at=raw.get("generated_at") or SourceCatalog().generated_at,
        environment=str(raw.get("environment", "development")),
        scouts=scouts,
        brands=brands,
        sources=sources,
        categories=categories,
        metadata=raw.get("metadata") or {},
    )

    result = CatalogValidationResult(
        valid=not errors and not (config.treat_warnings_as_errors and warnings),
        errors=errors,
        warnings=warnings,
        normalized_catalog=normalized_catalog,
        source_count=len(sources),
        scout_count=len(scouts),
        brand_count=len(brands),
        category_count=len(categories),
    )

    return result


def _load_connector_registry(config):
    try:
        from collector_intelligence.connectors import build_default_manager
        return build_default_manager()
    except Exception:
        return None


def _build_category(entry, index, config):
    errors, warnings = [], []
    if not isinstance(entry, dict):
        return None, [_err(f"categories[{index}]", "INVALID_ENTRY_TYPE", "Category entry must be a mapping.")], []

    category_id = normalize_id(entry.get("category_id")) if config.normalize_ids else entry.get("category_id")
    if not category_id:
        errors.append(_err(f"categories[{index}]", "MISSING_CATEGORY_ID", "category_id is required."))
        return None, errors, warnings

    name = normalize_text_field(entry.get("name")) or category_id

    metadata = entry.get("metadata") or {}
    if not _is_json_compatible(metadata):
        errors.append(_err(f"categories.{category_id}.metadata", "METADATA_NOT_JSON_COMPATIBLE", "metadata must be JSON-compatible."))

    return CategoryDefinition(
        category_id=category_id,
        name=name,
        parent_category_id=(normalize_id(entry.get("parent_category_id")) if entry.get("parent_category_id") else None),
        description=normalize_text_field(entry.get("description")),
        enabled=bool(entry.get("enabled", True)),
        metadata=metadata,
    ), errors, warnings


def _detect_category_cycles(categories):
    errors = []
    for start_id in categories:
        seen = set()
        current = start_id
        while current:
            if current in seen:
                errors.append(_err(f"categories.{start_id}", "CATEGORY_CYCLE", f"Category hierarchy starting at {start_id!r} contains a cycle."))
                break
            seen.add(current)
            category = categories.get(current)
            current = category.parent_category_id if category else None
    return errors


def _build_brand(entry, index, config, categories):
    errors, warnings = [], []
    if not isinstance(entry, dict):
        return None, [_err(f"brands[{index}]", "INVALID_ENTRY_TYPE", "Brand entry must be a mapping.")], []

    brand_id = normalize_id(entry.get("brand_id")) if config.normalize_ids else entry.get("brand_id")
    if not brand_id:
        errors.append(_err(f"brands[{index}]", "MISSING_BRAND_ID", "brand_id is required."))
        return None, errors, warnings

    name = normalize_text_field(entry.get("name")) or brand_id

    priority_value, priority_valid = normalize_priority(entry.get("priority", "medium"))
    if not priority_valid:
        errors.append(_err(f"brands.{brand_id}.priority", "INVALID_PRIORITY", f"{entry.get('priority')!r} is not a valid priority."))

    category_ids = [normalize_id(c) for c in (entry.get("categories") or [])]
    for category_id in category_ids:
        if category_id not in categories:
            errors.append(_err(f"brands.{brand_id}.categories", "MISSING_CATEGORY_REFERENCE", f"brand {brand_id!r} references unknown category_id {category_id!r}."))

    domains = [normalize_domain(d) for d in (entry.get("official_domains") or [])]
    for domain in domains:
        if domain and ("." not in domain or " " in domain):
            errors.append(_err(f"brands.{brand_id}.official_domains", "INVALID_DOMAIN", f"{domain!r} does not look like a valid domain."))

    metadata = entry.get("metadata") or {}
    if not _is_json_compatible(metadata):
        errors.append(_err(f"brands.{brand_id}.metadata", "METADATA_NOT_JSON_COMPATIBLE", "metadata must be JSON-compatible."))

    region = normalize_region(entry.get("region")) if entry.get("region") else None
    if config.allowed_regions and region and region not in config.allowed_regions:
        warnings.append(_warn(f"brands.{brand_id}.region", "REGION_NOT_ALLOWLISTED", f"{region!r} is not in the configured allowed_regions."))

    return BrandDefinition(
        brand_id=brand_id,
        name=name,
        aliases=normalize_id_list_or_text(entry.get("aliases")),
        categories=category_ids,
        official_domains=[d for d in domains if d],
        region=region,
        enabled=bool(entry.get("enabled", True)),
        priority=priority_value,
        metadata=metadata,
    ), errors, warnings


def normalize_id_list_or_text(values):
    from collector_intelligence.catalog_normalization import normalize_aliases
    return normalize_aliases(values or [])


def _build_expected_evidence(entry, path, errors, warnings):
    entry = entry or {}
    if not isinstance(entry, dict):
        errors.append(_err(path, "INVALID_EXPECTED_EVIDENCE", "expected_evidence must be a mapping."))
        return ExpectedEvidenceDefinition()

    return ExpectedEvidenceDefinition(
        evidence_types=list(entry.get("evidence_types") or []),
        likely_fields=list(entry.get("likely_fields") or []),
        official_status=entry.get("official_status"),
        price_kind=entry.get("price_kind"),
        expected_unit_scope=entry.get("expected_unit_scope"),
        supports_release_date=bool(entry.get("supports_release_date", False)),
        supports_availability=bool(entry.get("supports_availability", False)),
        supports_purchase_limits=bool(entry.get("supports_purchase_limits", False)),
        supports_market_price=bool(entry.get("supports_market_price", False)),
        supports_event_details=bool(entry.get("supports_event_details", False)),
        notes=normalize_text_field(entry.get("notes")),
    )


def _build_health_policy(entry, path, errors):
    entry = entry or {}
    if not isinstance(entry, dict):
        errors.append(_err(path, "INVALID_HEALTH_POLICY", "health_policy must be a mapping."))
        return SourceHealthPolicy()

    policy = SourceHealthPolicy(
        max_consecutive_failures=int(entry.get("max_consecutive_failures", 5)),
        disable_after_failures=int(entry.get("disable_after_failures", 10)),
        stale_after=float(entry.get("stale_after", 168.0)),
        warning_after=float(entry.get("warning_after", 48.0)),
        expected_update_frequency=entry.get("expected_update_frequency"),
        temporary_failure_backoff=entry.get("temporary_failure_backoff", "exponential"),
        permanent_failure_action=entry.get("permanent_failure_action", "pause"),
    )

    for field_name in ("max_consecutive_failures", "disable_after_failures", "stale_after", "warning_after"):
        if getattr(policy, field_name) < 0:
            errors.append(_err(f"{path}.{field_name}", "NEGATIVE_HEALTH_THRESHOLD", f"{field_name} cannot be negative."))

    return policy


def _build_schedule(entry, path, errors):
    entry = entry or {}
    if not isinstance(entry, dict):
        errors.append(_err(path, "INVALID_SCHEDULE", "schedule must be a mapping."))
        return ScheduleSpec()

    mode = entry.get("mode")
    cron_expression = entry.get("cron_expression")

    if mode is not None:
        normalized_mode, is_valid = normalize_schedule_mode(mode)
        if not is_valid:
            errors.append(_err(f"{path}.mode", "INVALID_SCHEDULE_MODE", f"{mode!r} is not a valid schedule mode."))
        mode = normalized_mode

    if mode == "cron" and not cron_expression:
        errors.append(_err(f"{path}.cron_expression", "MISSING_CRON_EXPRESSION", "cron mode requires cron_expression."))

    return ScheduleSpec(mode=mode, cron_expression=cron_expression)


def _build_source(entry, index, config, categories, brands, connector_registry):
    errors, warnings = [], []
    if not isinstance(entry, dict):
        return None, [_err(f"sources[{index}]", "INVALID_ENTRY_TYPE", "Source entry must be a mapping.")], []

    source_id = normalize_id(entry.get("source_id")) if config.normalize_ids else entry.get("source_id")
    if not source_id:
        errors.append(_err(f"sources[{index}]", "MISSING_SOURCE_ID", "source_id is required."))
        return None, errors, warnings

    path = f"sources.{source_id}"
    name = normalize_text_field(entry.get("name")) or source_id

    source_type, source_type_valid = normalize_catalog_source_type(entry.get("source_type"))
    if not source_type_valid:
        errors.append(_err(f"{path}.source_type", "INVALID_SOURCE_TYPE", f"{entry.get('source_type')!r} is not a valid source_type."))

    authority_level, authority_valid = normalize_authority_level(entry.get("authority_level"))
    if not authority_valid:
        errors.append(_err(f"{path}.authority_level", "INVALID_AUTHORITY_LEVEL", f"{entry.get('authority_level')!r} is not a valid authority_level."))

    lifecycle_state, lifecycle_valid = normalize_lifecycle_state(entry.get("lifecycle_state"))
    if not lifecycle_valid:
        errors.append(_err(f"{path}.lifecycle_state", "INVALID_LIFECYCLE_STATE", f"{entry.get('lifecycle_state')!r} is not a valid lifecycle_state."))

    allowed_connectors = config.allowed_connector_names or VALID_CONNECTOR_NAMES
    connector_type = entry.get("connector_type")
    if connector_type:
        connector_type, connector_valid = normalize_connector_name(connector_type, allowed_connectors)
        if not connector_valid:
            errors.append(_err(f"{path}.connector_type", "UNKNOWN_CONNECTOR", f"{entry.get('connector_type')!r} is not a known/allowed connector."))
        elif connector_registry is not None and not connector_registry.has(connector_type):
            errors.append(_err(f"{path}.connector_type", "UNKNOWN_CONNECTOR", f"Connector {connector_type!r} is not registered."))
        elif connector_registry is not None and connector_registry.has(connector_type) and source_type_valid:
            descriptor_type = CATALOG_SOURCE_TYPE_TO_DESCRIPTOR_TYPE.get(source_type)
            connector = connector_registry.get(connector_type)
            if descriptor_type and descriptor_type not in connector.supported_source_types:
                errors.append(_err(
                    f"{path}.connector_type", "CONNECTOR_SOURCE_TYPE_MISMATCH",
                    f"Connector {connector_type!r} does not support source_type "
                    f"{source_type!r} (expects descriptor type {descriptor_type!r}, "
                    f"connector supports {list(connector.supported_source_types)}).",
                ))
    elif source_type_valid and CATALOG_SOURCE_TYPE_TO_DESCRIPTOR_TYPE.get(source_type) is not None:
        errors.append(_err(f"{path}.connector_type", "MISSING_CONNECTOR_TYPE", f"source_type {source_type!r} requires a connector_type."))

    url = entry.get("url")
    normalized_url = None
    if url:
        normalized_url, url_valid = normalize_catalog_url(url, config.allowed_url_schemes)
        if not url_valid:
            errors.append(_err(f"{path}.url", "INVALID_URL", f"{url!r} is not a valid URL with an allowed scheme."))
            normalized_url = url
    elif source_type_valid and CATALOG_SOURCE_TYPE_TO_DESCRIPTOR_TYPE.get(source_type) is not None:
        errors.append(_err(f"{path}.url", "MISSING_URL", f"source_type {source_type!r} requires a url."))

    brand_id = normalize_id(entry.get("brand_id")) if entry.get("brand_id") else None
    if brand_id and brand_id not in brands:
        errors.append(_err(f"{path}.brand_id", "MISSING_BRAND_REFERENCE", f"brand_id {brand_id!r} does not exist."))

    category_ids = [normalize_id(c) for c in (entry.get("category_ids") or [])]
    for category_id in category_ids:
        if category_id not in categories:
            errors.append(_err(f"{path}.category_ids", "MISSING_CATEGORY_REFERENCE", f"category_id {category_id!r} does not exist."))

    scout_ids = [normalize_id(s) for s in (entry.get("scout_ids") or [])]

    priority_value, priority_valid = normalize_priority(entry.get("priority", "medium"))
    if not priority_valid:
        errors.append(_err(f"{path}.priority", "INVALID_PRIORITY", f"{entry.get('priority')!r} is not a valid priority."))

    schedule = _build_schedule(entry.get("schedule"), f"{path}.schedule", errors)
    connector_config = normalize_connector_config_keys(entry.get("connector_config") or {})
    if not _is_json_compatible(connector_config):
        errors.append(_err(f"{path}.connector_config", "CONNECTOR_CONFIG_NOT_JSON_COMPATIBLE", "connector_config must be JSON-compatible."))

    expected_evidence = _build_expected_evidence(entry.get("expected_evidence"), f"{path}.expected_evidence", errors, warnings)
    health_policy = _build_health_policy(entry.get("health_policy"), f"{path}.health_policy", errors)

    region = normalize_region(entry.get("region")) if entry.get("region") else None
    if config.allowed_regions and region and region not in config.allowed_regions:
        warnings.append(_warn(f"{path}.region", "REGION_NOT_ALLOWLISTED", f"{region!r} is not in the configured allowed_regions."))

    language = normalize_language(entry.get("language")) if entry.get("language") else None
    if config.allowed_languages and language and language not in config.allowed_languages:
        warnings.append(_warn(f"{path}.language", "LANGUAGE_NOT_ALLOWLISTED", f"{language!r} is not in the configured allowed_languages."))

    metadata = entry.get("metadata") or {}
    if not _is_json_compatible(metadata):
        errors.append(_err(f"{path}.metadata", "METADATA_NOT_JSON_COMPATIBLE", "metadata must be JSON-compatible."))

    if lifecycle_state == "deprecated":
        warnings.append(_warn(path, "DEPRECATED_SOURCE", f"Source {source_id!r} is deprecated."))

    priority_value = priority_value if priority_valid else "medium"

    return SourceDefinition(
        source_id=source_id,
        name=name,
        enabled=bool(entry.get("enabled", True)),
        source_type=source_type if source_type_valid else "manual_report",
        authority_level=authority_level if authority_valid else "manual_untrusted",
        connector_type=connector_type,
        connector_version=entry.get("connector_version"),
        url=normalized_url,
        brand_id=brand_id,
        scout_ids=scout_ids,
        category_ids=category_ids,
        schedule=schedule,
        connector_config=connector_config,
        expected_evidence=expected_evidence,
        region=region,
        language=language,
        lifecycle_state=lifecycle_state if lifecycle_valid else "proposed",
        health_policy=health_policy,
        tags=normalize_tags(entry.get("tags")),
        notes=normalize_text_field(entry.get("notes")),
        metadata=metadata,
    ), errors, warnings


def _build_scout(entry, index, config, categories, brands, sources):
    errors, warnings = [], []
    if not isinstance(entry, dict):
        return None, [_err(f"scouts[{index}]", "INVALID_ENTRY_TYPE", "Scout entry must be a mapping.")], []

    scout_id = normalize_id(entry.get("scout_id")) if config.normalize_ids else entry.get("scout_id")
    if not scout_id:
        errors.append(_err(f"scouts[{index}]", "MISSING_SCOUT_ID", "scout_id is required."))
        return None, errors, warnings

    path = f"scouts.{scout_id}"
    name = normalize_text_field(entry.get("name")) or scout_id

    priority_value, priority_valid = normalize_priority(entry.get("priority", "medium"))
    if not priority_valid:
        errors.append(_err(f"{path}.priority", "INVALID_PRIORITY", f"{entry.get('priority')!r} is not a valid priority."))

    category_ids = [normalize_id(c) for c in (entry.get("categories") or [])]
    for category_id in category_ids:
        if category_id not in categories:
            errors.append(_err(f"{path}.categories", "MISSING_CATEGORY_REFERENCE", f"category_id {category_id!r} does not exist."))

    brand_ids = [normalize_id(b) for b in (entry.get("brands") or [])]
    for brand_id in brand_ids:
        if brand_id not in brands:
            errors.append(_err(f"{path}.brands", "MISSING_BRAND_REFERENCE", f"brand_id {brand_id!r} does not exist."))

    source_ids = [normalize_id(s) for s in (entry.get("source_ids") or [])]
    for source_id in source_ids:
        if source_id not in sources:
            errors.append(_err(f"{path}.source_ids", "MISSING_SOURCE_REFERENCE", f"source_id {source_id!r} does not exist."))

    schedule = _build_schedule(entry.get("default_schedule"), f"{path}.default_schedule", errors)
    connector_config = normalize_connector_config_keys(entry.get("default_connector_config") or {})
    if not _is_json_compatible(connector_config):
        errors.append(_err(f"{path}.default_connector_config", "CONNECTOR_CONFIG_NOT_JSON_COMPATIBLE", "default_connector_config must be JSON-compatible."))

    metadata = entry.get("metadata") or {}
    if not _is_json_compatible(metadata):
        errors.append(_err(f"{path}.metadata", "METADATA_NOT_JSON_COMPATIBLE", "metadata must be JSON-compatible."))

    return ScoutDefinition(
        scout_id=scout_id,
        name=name,
        description=normalize_text_field(entry.get("description")),
        enabled=bool(entry.get("enabled", True)),
        priority=priority_value if priority_valid else "medium",
        categories=category_ids,
        brands=brand_ids,
        source_ids=source_ids,
        default_schedule=schedule,
        default_connector_config=connector_config,
        tags=normalize_tags(entry.get("tags")),
        owner=normalize_text_field(entry.get("owner")),
        notes=normalize_text_field(entry.get("notes")),
        metadata=metadata,
    ), errors, warnings
