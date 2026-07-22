"""
Atlas v21 - Module 7: catalog loading.

Accepts a Python dict, raw JSON/YAML text, or a file path (.json,
.yaml/.yml). YAML uses yaml.safe_load only - never a permissive
loader capable of deserializing arbitrary Python objects. If PyYAML
isn't installed, YAML files fail with a clear, actionable error
rather than a heavy dependency being pulled in just for this.
"""

import json
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class CatalogLoadError(Exception):
    def __init__(self, message, validation_result=None):
        super().__init__(message)
        self.validation_result = validation_result


class UnsafePathError(CatalogLoadError):
    pass


def yaml_available():
    return YAML_AVAILABLE


def _looks_like_path(value):
    text = str(value)
    if "\n" in text:
        return False
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return False
    return True


def _safe_yaml_load(text):
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CatalogLoadError(f"Could not parse YAML: {exc}") from exc


def _parse_text(text, config):
    if len(text.encode("utf-8")) > config.maximum_catalog_size_bytes:
        raise CatalogLoadError(
            f"Catalog text exceeds the configured maximum of "
            f"{config.maximum_catalog_size_bytes} bytes."
        )

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if YAML_AVAILABLE:
        return _safe_yaml_load(text)

    raise CatalogLoadError(
        "Could not parse catalog text as JSON, and PyYAML is not installed "
        "to attempt YAML."
    )


def _read_path(path, config):
    path_obj = Path(path).resolve()

    if not path_obj.exists():
        raise UnsafePathError(f"{path!r} does not exist.")

    if not path_obj.is_file():
        raise UnsafePathError(f"{path!r} is not a regular file.")

    size = path_obj.stat().st_size
    if size > config.maximum_catalog_size_bytes:
        raise CatalogLoadError(
            f"Catalog file {path!r} is {size} bytes, exceeding the "
            f"configured maximum of {config.maximum_catalog_size_bytes} bytes."
        )

    try:
        text = path_obj.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CatalogLoadError(f"Catalog file {path!r} is not valid UTF-8: {exc}") from exc

    suffix = path_obj.suffix.lower()

    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise CatalogLoadError(f"Could not parse JSON catalog {path!r}: {exc}") from exc

    if suffix in (".yaml", ".yml"):
        if not YAML_AVAILABLE:
            raise CatalogLoadError(
                f"Catalog file {path!r} is YAML but PyYAML is not installed. "
                f"Install pyyaml, or provide a .json catalog instead."
            )
        return _safe_yaml_load(text)

    supported = ".json" + (", .yaml, .yml" if YAML_AVAILABLE else " (PyYAML not installed)")
    raise CatalogLoadError(f"Unsupported catalog file type {suffix!r} for {path!r} - supported: {supported}")


def load_catalog(path_or_data, config=None):
    """
    Loads, validates, and normalizes a catalog. Raises CatalogLoadError
    (with `.validation_result` attached) if the catalog doesn't
    validate - callers who want issues without an exception should call
    validate_catalog() directly instead.
    """
    from collector_intelligence.catalog_config import CatalogConfig
    from collector_intelligence.catalog_models import SourceCatalog
    from collector_intelligence.catalog_validation import validate_catalog

    config = config or CatalogConfig()

    if isinstance(path_or_data, SourceCatalog):
        raw_data = path_or_data
    elif isinstance(path_or_data, Path):
        raw_data = _read_path(path_or_data, config)
    elif isinstance(path_or_data, str) and _looks_like_path(path_or_data):
        raw_data = _read_path(path_or_data, config)
    elif isinstance(path_or_data, str):
        raw_data = _parse_text(path_or_data, config)
    else:
        raw_data = path_or_data

    result = validate_catalog(raw_data, config)

    if not result.valid:
        raise CatalogLoadError(
            f"Catalog failed validation with {len(result.errors)} error(s) "
            f"and {len(result.warnings)} warning(s).",
            validation_result=result,
        )

    return result.normalized_catalog
