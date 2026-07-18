import acquisition.requests_retriever as requests_retriever_module
import scouts.pokemon.internet_scout as internet_scout_module
from acquisition.models import RawContent
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


class FakeRetriever:
    """
    Test double giving per-source control over fetch() results,
    independent of RequestsRetriever's own internal handling of
    requests.RequestException. Used to exercise AcquisitionService's
    own retrieval-stage isolation directly.
    """

    def __init__(self, responses):
        self.responses = responses

    def fetch(self, source):
        response = self.responses[source["name"]]

        if isinstance(response, Exception):
            raise response

        return response


def make_source(name):
    return {
        "name": name,
        "url": f"https://www.pokemon.com/{name}",
        "base_url": "https://www.pokemon.com",
        "allowed_paths": ["/"],
    }


def make_raw_content(source, content):
    return RawContent(
        source_name=source["name"],
        url=source["url"],
        content=content,
        fetched_at="2026-07-18T00:00:00+00:00",
        status=200,
        content_type="text/html",
    )


def test_collect_returns_items_from_all_sources_when_everything_succeeds(
    monkeypatch,
):
    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    source_a = make_source("source_a")
    source_b = make_source("source_b")

    retriever = FakeRetriever({
        "source_a": make_raw_content(source_a, "A"),
        "source_b": make_raw_content(source_b, "B"),
    })

    def extractor(html, source):
        return [{"title": f"item-from-{html}"}]

    service = AcquisitionService(retriever=retriever)

    items = service.collect(
        sources=[source_a, source_b],
        extractors={"Test extractor": extractor},
    )

    assert items == [
        {"title": "item-from-A"},
        {"title": "item-from-B"},
    ]


def test_retrieval_failure_for_one_source_does_not_block_later_sources(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    source_a = make_source("source_a")
    source_b = make_source("source_b")

    retriever = FakeRetriever({
        "source_a": ConnectionError(
            "network unreachable"
        ),
        "source_b": make_raw_content(source_b, "B"),
    })

    def extractor(html, source):
        return [{"title": f"item-from-{html}"}]

    service = AcquisitionService(retriever=retriever)

    items = service.collect(
        sources=[source_a, source_b],
        extractors={"Test extractor": extractor},
    )

    assert items == [{"title": "item-from-B"}]

    captured = capsys.readouterr()
    assert (
        "[AcquisitionService] retrieval failed "
        "for source_a" in captured.out
    )
    assert "ConnectionError" in captured.out
    assert "network unreachable" in captured.out


def test_items_collected_before_a_later_retrieval_failure_are_retained(
    monkeypatch,
):
    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    source_a = make_source("source_a")
    source_b = make_source("source_b")

    retriever = FakeRetriever({
        "source_a": make_raw_content(source_a, "A"),
        "source_b": ConnectionError(
            "network unreachable"
        ),
    })

    def extractor(html, source):
        return [{"title": f"item-from-{html}"}]

    service = AcquisitionService(retriever=retriever)

    items = service.collect(
        sources=[source_a, source_b],
        extractors={"Test extractor": extractor},
    )

    assert items == [{"title": "item-from-A"}]


def test_structured_extractor_failure_does_not_block_html_extractor_or_later_sources(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    source_a = make_source("source_a")
    source_b = make_source("source_b")

    retriever = FakeRetriever({
        "source_a": make_raw_content(source_a, "A"),
        "source_b": make_raw_content(source_b, "B"),
    })

    def flaky_structured_extractor(html, source):
        if source["name"] == "source_a":
            raise ValueError("malformed JSON-LD")

        return [{"title": f"structured-{html}"}]

    def html_extractor(html, source):
        return [{"title": f"html-{html}"}]

    service = AcquisitionService(retriever=retriever)

    items = service.collect(
        sources=[source_a, source_b],
        extractors={
            "Structured candidates": (
                flaky_structured_extractor
            ),
            "HTML candidates": html_extractor,
        },
    )

    assert items == [
        {"title": "html-A"},
        {"title": "structured-B"},
        {"title": "html-B"},
    ]

    captured = capsys.readouterr()
    assert (
        "[AcquisitionService] Structured candidates "
        "failed for source_a" in captured.out
    )
    assert "ValueError" in captured.out


def test_html_extractor_failure_does_not_block_structured_extractor_or_later_sources(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    source_a = make_source("source_a")
    source_b = make_source("source_b")

    retriever = FakeRetriever({
        "source_a": make_raw_content(source_a, "A"),
        "source_b": make_raw_content(source_b, "B"),
    })

    def flaky_html_extractor(html, source):
        if source["name"] == "source_a":
            raise ValueError("malformed markup")

        return [{"title": f"html-{html}"}]

    def structured_extractor(html, source):
        return [{"title": f"structured-{html}"}]

    service = AcquisitionService(retriever=retriever)

    items = service.collect(
        sources=[source_a, source_b],
        extractors={
            "HTML candidates": flaky_html_extractor,
            "Structured candidates": (
                structured_extractor
            ),
        },
    )

    assert items == [
        {"title": "structured-A"},
        {"title": "html-B"},
        {"title": "structured-B"},
    ]

    captured = capsys.readouterr()
    assert (
        "[AcquisitionService] HTML candidates "
        "failed for source_a" in captured.out
    )
    assert "ValueError" in captured.out


def test_empty_content_skips_extraction_without_logging_a_failure(
    capsys,
):
    source_a = make_source("source_a")

    retriever = FakeRetriever({
        "source_a": make_raw_content(
            source_a,
            content=None,
        ),
    })

    calls = {"count": 0}

    def extractor(html, source):
        calls["count"] += 1
        return [{"title": "should-not-be-called"}]

    service = AcquisitionService(retriever=retriever)

    items = service.collect(
        sources=[source_a],
        extractors={"Test extractor": extractor},
    )

    assert items == []
    assert calls["count"] == 0

    captured = capsys.readouterr()
    assert "[AcquisitionService]" not in captured.out


def test_return_type_remains_a_plain_list_when_a_source_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        "acquisition.service.time.sleep",
        lambda seconds: None,
    )

    source_a = make_source("source_a")
    source_b = make_source("source_b")

    retriever = FakeRetriever({
        "source_a": ConnectionError(
            "network unreachable"
        ),
        "source_b": make_raw_content(source_b, "B"),
    })

    def extractor(html, source):
        return [{"title": f"item-from-{html}"}]

    service = AcquisitionService(retriever=retriever)

    items = service.collect(
        sources=[source_a, source_b],
        extractors={"Test extractor": extractor},
    )

    assert type(items) is list
    assert items == [{"title": "item-from-B"}]
