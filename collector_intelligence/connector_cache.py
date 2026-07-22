"""
Atlas v21 - Module 6: fetch caching.

MemoryCache is the default, always-available implementation.
DiskCache is an optional interface with one simple JSON-file-backed
reference implementation - connectors never depend on disk caching
directly, only on the CacheBackend protocol.
"""

import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def compute_content_hash(text):
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


@dataclass
class CacheEntry:
    url: str
    body: str
    content_hash: str
    etag: str | None = None
    last_modified: str | None = None
    fetched_at: str = ""
    content_type: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class CacheBackend(ABC):
    @abstractmethod
    def get(self, url):
        ...

    @abstractmethod
    def set(self, url, entry):
        ...

    @abstractmethod
    def invalidate(self, url):
        ...

    @abstractmethod
    def all_hashes(self):
        """Returns {url: content_hash} for every cached entry - used for
        cross-source duplicate detection."""
        ...


class MemoryCache(CacheBackend):
    def __init__(self):
        self._store = {}

    def get(self, url):
        return self._store.get(url)

    def set(self, url, entry):
        self._store[url] = entry

    def invalidate(self, url):
        self._store.pop(url, None)

    def all_hashes(self):
        return {url: entry.content_hash for url, entry in self._store.items()}

    def clear(self):
        self._store.clear()


class FileDiskCache(CacheBackend):
    """
    Reference disk-cache implementation: one JSON file per URL, keyed
    by a hash of the URL, inside `directory`. Not used by default -
    connectors accept any CacheBackend, this is just a concrete option.
    """

    def __init__(self, directory):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, url):
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return os.path.join(self.directory, f"{key}.json")

    def get(self, url):
        path = self._path(url)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return CacheEntry.from_dict(json.load(f))

    def set(self, url, entry):
        with open(self._path(url), "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f)

    def invalidate(self, url):
        path = self._path(url)
        if os.path.exists(path):
            os.remove(path)

    def all_hashes(self):
        hashes = {}
        for filename in os.listdir(self.directory):
            if not filename.endswith(".json"):
                continue
            with open(os.path.join(self.directory, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
                hashes[data["url"]] = data["content_hash"]
        return hashes


def is_stale(entry, ttl_seconds, now=None):
    if entry is None:
        return True

    now = now or datetime.now(timezone.utc)
    try:
        fetched_at = datetime.fromisoformat(entry.fetched_at)
    except (ValueError, TypeError):
        return True

    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    age_seconds = (now - fetched_at).total_seconds()
    return age_seconds > ttl_seconds
