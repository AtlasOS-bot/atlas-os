"""
Atlas web server - server-side Supabase access.

The ONLY place in this codebase (besides GitHub Actions scripts) that
should ever hold SUPABASE_SERVICE_KEY. Browser JavaScript never sees
this module or its credentials - every dashboard read/write now goes
browser -> /api/* (this process) -> Supabase, never browser -> Supabase
directly.

SupabaseClient wraps plain `requests` calls against PostgREST (the
same library already used everywhere else in this repo - no new HTTP
dependency). FakeSupabaseClient is an in-memory stand-in with the same
interface, used by tests so nothing here ever needs a live database or
applied migrations to be tested.
"""

import uuid

import requests


class SupabaseError(RuntimeError):
    """Raised for any non-2xx response or network failure talking to
    Supabase. Callers (auth, rate limiting, API routes) catch this
    uniformly rather than branching on status codes themselves."""


class SupabaseClient:
    def __init__(self, base_url, service_key, session=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self.session = session or requests.Session()
        self.timeout = timeout

    def _headers(self, prefer=None):
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(self, method, table, params=None, json_body=None, prefer=None):
        url = f"{self.base_url}/rest/v1/{table}"
        try:
            response = self.session.request(
                method, url, params=params, json=json_body,
                headers=self._headers(prefer=prefer), timeout=self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise SupabaseError(f"{method} {table} failed: {exc}") from exc

        if response.status_code >= 300:
            raise SupabaseError(
                f"{method} {table} returned {response.status_code}: {response.text[:300]}"
            )

        if not response.content:
            return []
        return response.json()

    def select(self, table, filters=None, order=None, limit=None):
        params = {"select": "*", **_eq_filters(filters)}
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        return self._request("GET", table, params=params)

    def insert(self, table, row, prefer="return=representation"):
        result = self._request("POST", table, json_body=row, prefer=prefer)
        return result[0] if isinstance(result, list) and result else result

    def update(self, table, filters, changes, prefer="return=representation"):
        return self._request("PATCH", table, params=_eq_filters(filters), json_body=changes, prefer=prefer)

    def delete(self, table, filters):
        return self._request("DELETE", table, params=_eq_filters(filters), prefer="return=minimal")

    def select_lt(self, table, field, cutoff, extra_filters=None, order=None, limit=None):
        """Rows where `field` < `cutoff` (a PostgREST `lt.` filter - NULL
        values never match, same as SQL). Used for bounded cleanup
        queries (server/cleanup.py) - always pass `limit` there so a
        single call can never return an unbounded result set."""
        params = {"select": "id", field: f"lt.{cutoff}", **_eq_filters(extra_filters)}
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        return self._request("GET", table, params=params)


def _eq_filters(filters):
    """Builds PostgREST `eq.` filter params. Booleans need PostgREST's
    lowercase true/false, not Python's True/False - str(True) would
    otherwise produce the invalid filter `eq.True`."""
    params = {}
    for key, value in (filters or {}).items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        params[key] = f"eq.{value}"
    return params


class FakeSupabaseClient:
    """In-memory stand-in with the same select/insert/update/delete
    interface, for tests. Supports only equality filters - sufficient
    for everything this server needs (id/token-hash/opportunity-id
    lookups), matching PostgREST's `eq.` filters we actually use."""

    def __init__(self):
        self.tables = {}

    def _rows(self, table):
        return self.tables.setdefault(table, [])

    @staticmethod
    def _matches(row, filters):
        return all(row.get(key) == value for key, value in (filters or {}).items())

    def select(self, table, filters=None, order=None, limit=None):
        rows = [dict(row) for row in self._rows(table) if self._matches(row, filters)]
        if order:
            field, _, direction = order.partition(".")
            rows.sort(key=lambda r: r.get(field), reverse=(direction == "desc"))
        if limit is not None:
            rows = rows[:limit]
        return rows

    def insert(self, table, row, prefer="return=representation"):
        stored = dict(row)
        stored.setdefault("id", str(uuid.uuid4()))
        self._rows(table).append(stored)
        return dict(stored)

    def update(self, table, filters, changes, prefer="return=representation"):
        updated = []
        for row in self._rows(table):
            if self._matches(row, filters):
                row.update(changes)
                updated.append(dict(row))
        return updated

    def delete(self, table, filters):
        remaining = [row for row in self._rows(table) if not self._matches(row, filters)]
        self.tables[table] = remaining
        return []

    def select_lt(self, table, field, cutoff, extra_filters=None, order=None, limit=None):
        rows = [
            dict(row) for row in self._rows(table)
            if self._matches(row, extra_filters) and row.get(field) is not None and row.get(field) < cutoff
        ]
        if order:
            sort_field, _, direction = order.partition(".")
            rows.sort(key=lambda r: r.get(sort_field), reverse=(direction == "desc"))
        if limit is not None:
            rows = rows[:limit]
        return rows
