from datetime import datetime, timezone

import requests

from acquisition.models import RawContent


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class RequestsRetriever:

    def fetch(self, source):
        print(f"Scanning: {source['name']}")

        try:
            response = requests.get(
                source["url"],
                headers=REQUEST_HEADERS,
                timeout=30,
            )

            response.raise_for_status()

            print(
                f"HTTP {response.status_code} | "
                f"{len(response.text):,} characters"
            )

            return RawContent(
                source_name=source["name"],
                url=source["url"],
                content=response.text,
                fetched_at=utc_now(),
                status=response.status_code,
                content_type=response.headers.get(
                    "Content-Type"
                ),
            )

        except requests.RequestException as error:
            print(
                f"Source failed: {source['name']} | "
                f"{type(error).__name__}: {error}"
            )

            return RawContent(
                source_name=source["name"],
                url=source["url"],
                content=None,
                fetched_at=utc_now(),
                status=None,
                content_type=None,
            )


def utc_now():
    return datetime.now(timezone.utc).isoformat()
