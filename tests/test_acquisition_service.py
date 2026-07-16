import acquisition.requests_retriever as requests_retriever_module
import scouts.pokemon.internet_scout as internet_scout_module
from acquisition.requests_retriever import RequestsRetriever
from acquisition.service import AcquisitionService
from scouts.pokemon.internet_scout import (
    collect_official_pokemon_items,
    extract_html_items,
)


class FakeResponse:

    def __init__(self, status_code, text, content_type):
        self.status_code = status_code
        self.text = text
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests_retriever_module.requests.HTTPError(
                f"HTTP {self.status_code}"
            )


SOURCE = {
    "name": "test_source",
    "url": (
        "https://www.pokemon.com/"
        "us/pokemon-tcg/product-gallery"
    ),
    "base_url": "https://www.pokemon.com",
    "allowed_paths": [
        "/us/pokemon-tcg/product-gallery/",
    ],
}

SAMPLE_HTML = """
<html>
    <body>
        <a href="/us/pokemon-tcg/product-gallery/test-etb">
            Mega Evolution Test Elite Trainer Box
        </a>

        <a href="/us/privacy">
            Privacy
        </a>
    </body>
</html>
"""


def test_requests_retriever_success_returns_expected_raw_content(
    monkeypatch,
):
    def fake_get(url, headers, timeout):
        return FakeResponse(
            status_code=200,
            text=SAMPLE_HTML,
            content_type="text/html",
        )

    monkeypatch.setattr(
        requests_retriever_module.requests,
        "get",
        fake_get,
    )

    raw_content = RequestsRetriever().fetch(SOURCE)

    assert raw_content.source_name == "test_source"
    assert raw_content.url == SOURCE["url"]
    assert raw_content.content == SAMPLE_HTML
    assert raw_content.status == 200
    assert raw_content.content_type == "text/html"
    assert raw_content.fetched_at is not None


def test_requests_retriever_failure_returns_none_content(
    monkeypatch,
):
    def fake_get(url, headers, timeout):
        return FakeResponse(
            status_code=503,
            text="",
            content_type="text/html",
        )

    monkeypatch.setattr(
        requests_retriever_module.requests,
        "get",
        fake_get,
    )

    raw_content = RequestsRetriever().fetch(SOURCE)

    assert raw_content.content is None
    assert raw_content.status is None
    assert raw_content.content_type is None
    assert raw_content.fetched_at is not None


def test_acquisition_service_extraction_matches_direct_call(
    monkeypatch,
):
    def fake_get(url, headers, timeout):
        return FakeResponse(
            status_code=200,
            text=SAMPLE_HTML,
            content_type="text/html",
        )

    monkeypatch.setattr(
        requests_retriever_module.requests,
        "get",
        fake_get,
    )

    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    direct_items = extract_html_items(
        html=SAMPLE_HTML,
        source=SOURCE,
    )

    service = AcquisitionService(
        retriever=RequestsRetriever()
    )

    service_items = service.collect(
        sources=[SOURCE],
        extractors={
            "HTML candidates": extract_html_items,
        },
    )

    assert service_items == direct_items
    assert len(service_items) == 1
    assert (
        service_items[0]["title"]
        == "Mega Evolution Test Elite Trainer Box"
    )


def test_collect_official_pokemon_items_uses_acquisition_service(
    monkeypatch,
):
    def fake_get(url, headers, timeout):
        return FakeResponse(
            status_code=200,
            text=SAMPLE_HTML,
            content_type="text/html",
        )

    monkeypatch.setattr(
        requests_retriever_module.requests,
        "get",
        fake_get,
    )

    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    monkeypatch.setattr(
        internet_scout_module,
        "POKEMON_SOURCES",
        [SOURCE],
    )

    items = collect_official_pokemon_items()

    assert len(items) == 1
    assert (
        items[0]["title"]
        == "Mega Evolution Test Elite Trainer Box"
    )
