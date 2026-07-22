"""
Atlas v21 - Module 6: HTTP client wrapper.

All network access goes through a Transport abstraction so tests never
touch the real network: RequestsTransport is the production
implementation (built on the `requests` library, no browser
automation involved); FakeTransport is a deterministic, queue-driven
test double that lets tests script exact response sequences (e.g. a
500 followed by a 200, to exercise retry logic).
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from collector_intelligence.connector_models import ConnectorError, FetchResult

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------
# Transport abstraction
# ---------------------------------------------------------------

@dataclass
class RawResponse:
    status_code: int
    headers: dict
    body: bytes
    url: str


class TransportError(Exception):
    """Base for transport-level failures (never a Module error type
    itself - HTTPClient translates these into ConnectorError)."""


class TransportTimeout(TransportError):
    pass


class TransportNetworkError(TransportError):
    pass


class TransportSSLError(TransportError):
    pass


class Transport(ABC):
    @abstractmethod
    def request(self, method, url, headers, timeout, verify_ssl):
        """Returns a RawResponse or raises a TransportError subclass."""
        ...


class RequestsTransport(Transport):
    """Production transport - real HTTP, only ever used outside tests."""

    def request(self, method, url, headers, timeout, verify_ssl):
        import requests
        from requests.exceptions import (
            SSLError, Timeout, ConnectionError as RequestsConnectionError,
        )

        try:
            response = requests.request(
                method, url, headers=headers, timeout=timeout,
                verify=verify_ssl, allow_redirects=False,
            )
        except Timeout as exc:
            raise TransportTimeout(str(exc)) from exc
        except SSLError as exc:
            raise TransportSSLError(str(exc)) from exc
        except RequestsConnectionError as exc:
            raise TransportNetworkError(str(exc)) from exc

        return RawResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
            url=response.url,
        )


class FakeTransport(Transport):
    """
    Test double. `responses` maps a URL to either a single planned
    response/exception, or a list consumed in order (for scripting
    retry sequences). Never touches the network.
    """

    def __init__(self, responses=None):
        self._responses = responses or {}
        self.requests_made = []

    def plan(self, url, response_or_exception):
        self._responses.setdefault(url, [])
        if not isinstance(self._responses[url], list):
            self._responses[url] = [self._responses[url]]

        if isinstance(response_or_exception, list):
            self._responses[url].extend(response_or_exception)
        else:
            self._responses[url].append(response_or_exception)

    def request(self, method, url, headers, timeout, verify_ssl):
        self.requests_made.append({"method": method, "url": url, "headers": dict(headers)})

        planned = self._responses.get(url)

        if planned is None:
            raise TransportNetworkError(f"FakeTransport has no planned response for {url!r}")

        if isinstance(planned, list):
            if not planned:
                raise TransportNetworkError(f"FakeTransport exhausted responses for {url!r}")
            item = planned.pop(0) if len(planned) > 1 else planned[0]
        else:
            item = planned

        if isinstance(item, Exception):
            raise item

        return item


def make_response(status_code=200, headers=None, body="", url=None):
    return RawResponse(
        status_code=status_code,
        headers=headers or {},
        body=body.encode("utf-8") if isinstance(body, str) else body,
        url=url or "",
    )


# ---------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------

class HTTPClient:
    def __init__(self, transport=None, sleep_fn=None):
        self.transport = transport or RequestsTransport()
        self._sleep = sleep_fn or time.sleep

    def get(self, url, config, etag=None, last_modified=None):
        headers = {"User-Agent": config.user_agent, "Accept-Encoding": "gzip"}

        if config.use_etag and etag:
            headers["If-None-Match"] = etag
        if config.use_last_modified and last_modified:
            headers["If-Modified-Since"] = last_modified

        redirect_chain = [url]
        current_url = url
        attempts = 0
        started = time.perf_counter()

        while True:
            attempts += 1

            try:
                response = self.transport.request(
                    "GET", current_url, headers, config.timeout_seconds, config.verify_ssl,
                )
            except TransportTimeout:
                if attempts <= config.max_retries:
                    self._backoff(attempts, config)
                    continue
                return self._error_result(
                    url, "TIMEOUT", f"Request to {url} timed out after {attempts} attempt(s).",
                    attempts, started, recoverable=True,
                )
            except TransportSSLError as exc:
                return self._error_result(
                    url, "SSL_FAILURE", str(exc), attempts, started, recoverable=False,
                )
            except TransportNetworkError as exc:
                if attempts <= config.max_retries:
                    self._backoff(attempts, config)
                    continue
                return self._error_result(
                    url, "NETWORK", str(exc), attempts, started, recoverable=True,
                )

            if response.status_code == 304:
                return FetchResult(
                    success=True, url=url, status_code=304, not_modified=True,
                    from_cache=True, fetched_at=_utc_now(),
                    duration_ms=self._elapsed_ms(started), attempts=attempts,
                    redirect_chain=redirect_chain,
                )

            if response.status_code == 429:
                if attempts <= config.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    self._backoff(attempts, config, retry_after_header=retry_after)
                    continue
                return self._error_result(
                    url, "RATE_LIMITED", f"{url} responded 429 after {attempts} attempt(s).",
                    attempts, started, recoverable=True, status_code=429,
                )

            if response.status_code in (500, 502, 503, 504):
                if attempts <= config.max_retries:
                    self._backoff(attempts, config)
                    continue
                return self._error_result(
                    url, "TEMPORARY_FAILURE",
                    f"{url} responded {response.status_code} after {attempts} attempt(s).",
                    attempts, started, recoverable=True, status_code=response.status_code,
                )

            if response.status_code in (301, 302, 303, 307, 308):
                if not config.follow_redirects:
                    return self._error_result(
                        url, "PERMANENT_FAILURE",
                        f"{url} redirected but follow_redirects is disabled.",
                        attempts, started, recoverable=False, status_code=response.status_code,
                    )

                location = response.headers.get("Location") or response.headers.get("location")
                if not location:
                    return self._error_result(
                        url, "PERMANENT_FAILURE",
                        f"{url} returned a redirect status with no Location header.",
                        attempts, started, recoverable=False, status_code=response.status_code,
                    )

                if location in redirect_chain or len(redirect_chain) > config.max_redirects:
                    return self._error_result(
                        url, "REDIRECT_LOOP",
                        f"Redirect chain from {url} exceeded {config.max_redirects} hops "
                        f"or revisited a URL: {redirect_chain + [location]}",
                        attempts, started, recoverable=False,
                    )

                redirect_chain.append(location)
                current_url = location
                continue

            if response.status_code >= 400:
                return self._error_result(
                    url, "PERMANENT_FAILURE",
                    f"{url} responded with client error {response.status_code}.",
                    attempts, started, recoverable=False, status_code=response.status_code,
                )

            # --- success path ---

            if len(response.body) > config.max_payload_bytes:
                return self._error_result(
                    url, "OVERSIZED_PAYLOAD",
                    f"{url} response body ({len(response.body)} bytes) exceeds the "
                    f"configured maximum of {config.max_payload_bytes} bytes.",
                    attempts, started, recoverable=False, status_code=response.status_code,
                )

            content_type = _content_type_only(
                response.headers.get("Content-Type") or response.headers.get("content-type")
            )

            if content_type and config.allowed_mime_types and content_type not in config.allowed_mime_types:
                return self._error_result(
                    url, "UNSUPPORTED_CONTENT_TYPE",
                    f"{url} returned unsupported content type {content_type!r}.",
                    attempts, started, recoverable=False, status_code=response.status_code,
                )

            try:
                body_text = response.body.decode("utf-8")
            except UnicodeDecodeError:
                body_text = response.body.decode("utf-8", errors="replace")

            return FetchResult(
                success=True,
                url=response.url or current_url,
                status_code=response.status_code,
                body=body_text,
                content_type=content_type,
                headers=dict(response.headers),
                etag=response.headers.get("ETag") or response.headers.get("etag"),
                last_modified=(
                    response.headers.get("Last-Modified")
                    or response.headers.get("last-modified")
                ),
                fetched_at=_utc_now(),
                duration_ms=self._elapsed_ms(started),
                from_cache=False,
                redirect_chain=redirect_chain,
                attempts=attempts,
            )

    def _backoff(self, attempt, config, retry_after_header=None):
        if retry_after_header:
            try:
                delay = float(retry_after_header)
            except ValueError:
                delay = config.retry_backoff_base_seconds
        else:
            delay = min(
                config.retry_backoff_base_seconds * (2 ** (attempt - 1)),
                config.retry_backoff_max_seconds,
            )
        self._sleep(delay)

    @staticmethod
    def _elapsed_ms(started):
        return round((time.perf_counter() - started) * 1000, 3)

    def _error_result(
        self, url, error_type, message, attempts, started, recoverable, status_code=None,
    ):
        return FetchResult(
            success=False, url=url, status_code=status_code,
            fetched_at=_utc_now(), duration_ms=self._elapsed_ms(started),
            attempts=attempts,
            error=ConnectorError(
                error_type=error_type, message=message, recoverable=recoverable,
                status_code=status_code,
            ),
        )


def _content_type_only(header_value):
    if not header_value:
        return None
    return header_value.split(";")[0].strip().lower()
