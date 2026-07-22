"""
Atlas v21 - Module 5: adapter registry and automatic detection.

Detection is deliberately conservative: if two adapters are similarly
plausible for a payload, the registry refuses to guess. It returns an
ambiguous AdapterDetection instead, and callers must either supply an
explicit adapter name or treat the payload as requiring manual review.
"""

from collector_intelligence.ingestion_models import AdapterDetection


class UnknownAdapterError(Exception):
    pass


class AdapterRegistry:
    def __init__(self):
        self._adapters = {}

    def register(self, adapter):
        self._adapters[adapter.name] = adapter

    def unregister(self, name):
        self._adapters.pop(name, None)

    def get(self, name):
        adapter = self._adapters.get(name)
        if adapter is None:
            raise UnknownAdapterError(f"No adapter registered under {name!r}.")
        return adapter

    def has(self, name):
        return name in self._adapters

    def list_adapters(self):
        return list(self._adapters.values())

    def list_names(self):
        return sorted(self._adapters)

    def detect(self, payload, config):
        candidates = []

        for adapter in self._adapters.values():
            try:
                if not adapter.can_handle(payload):
                    continue
                confidence, reasons = adapter.detection_confidence(payload)
            except Exception:
                continue

            if confidence > 0:
                candidates.append((adapter.name, confidence, reasons))

        if not candidates:
            return AdapterDetection(
                adapter_name=None,
                confidence=0.0,
                reasons=["No registered adapter's can_handle() matched this payload."],
                ambiguous=False,
                alternatives=[],
            )

        candidates.sort(key=lambda c: c[1], reverse=True)
        best_name, best_confidence, best_reasons = candidates[0]
        alternatives = [name for name, _, _ in candidates]

        ambiguous = (
            len(candidates) > 1
            and (best_confidence - candidates[1][1]) < config.adapter_ambiguity_threshold
        )

        return AdapterDetection(
            adapter_name=None if ambiguous else best_name,
            confidence=best_confidence,
            reasons=best_reasons if not ambiguous else [
                f"Top candidates {candidates[0][0]!r} ({candidates[0][1]:.2f}) and "
                f"{candidates[1][0]!r} ({candidates[1][1]:.2f}) are too close to "
                f"choose automatically."
            ],
            ambiguous=ambiguous,
            alternatives=alternatives,
        )


_default_registry = None


def get_default_registry():
    """
    Lazily builds and caches the registry pre-populated with every
    built-in adapter, so callers don't need to hand-register the
    standard set themselves.
    """
    global _default_registry

    if _default_registry is None:
        from collector_intelligence.adapters import build_default_registry
        _default_registry = build_default_registry()

    return _default_registry
