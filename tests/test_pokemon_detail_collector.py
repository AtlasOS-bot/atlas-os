from scouts.pokemon.detail_collector import (
    classify_detail_content,
    collect_pokemon_product_detail,
    extract_detail_fields,
    find_commerce_links,
    normalize_availability,
    normalize_price,
    resolve_commerce_url_from_gallery_html,
)


class FakeRetriever:
    """
    Maps URL -> HTML (or an Exception instance to raise), matching
    the DetailPageRetriever interface. No real network access.
    """

    def __init__(self, responses):
        self.responses = responses
        self.fetched_urls = []

    def fetch(self, url):
        self.fetched_urls.append(url)

        response = self.responses.get(url)

        if isinstance(response, Exception):
            raise response

        return response


STRUCTURED_PRODUCT_PAGE = """
<html>
<head>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Pokémon Center Exclusive Mega Dragonite ex ETB",
    "url": "https://www.pokemoncenter.com/product/12345-dragonite-etb",
    "description": "Elite trainer box with exclusive promo card.",
    "sku": "PC-ETB-DRAGONITE",
    "productID": "PC-ETB-DRAGONITE",
    "image": "/images/dragonite-etb.jpg",
    "offers": {
        "@type": "Offer",
        "price": "59.99",
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock"
    }
}
</script>
</head>
<body>
<p>Limit 2 per customer.</p>
</body>
</html>
"""

OUT_OF_STOCK_PAGE = """
<html>
<head>
<script type="application/ld+json">
{
    "@type": "Product",
    "name": "Pokémon Center Booster Bundle",
    "url": "https://www.pokemoncenter.com/product/booster-bundle",
    "sku": "PC-BB-001",
    "offers": {
        "price": "39.99",
        "priceCurrency": "USD",
        "availability": "https://schema.org/OutOfStock"
    }
}
</script>
</head>
<body></body>
</html>
"""

PREORDER_PAGE = """
<html>
<head>
<script type="application/ld+json">
{
    "@type": "Product",
    "name": "Pokémon Center Collection Box",
    "url": "https://www.pokemoncenter.com/product/collection-box",
    "offers": {
        "price": "89.99",
        "priceCurrency": "USD",
        "availability": "https://schema.org/PreOrder"
    }
}
</script>
</head>
<body></body>
</html>
"""

COMING_SOON_TEXT_ONLY_PAGE = """
<html>
<body>
<h1>Pokémon Center New Set</h1>
<p>This item is Coming Soon. Check back for availability.</p>
</body>
</html>
"""

MALFORMED_STRUCTURED_DATA_PAGE = """
<html>
<head>
<script type="application/ld+json">
{ this is not valid json at all ][
</script>
<meta property="og:title" content="Pokémon Center Fallback Item">
<meta property="og:price:amount" content="49.99">
<meta property="og:price:currency" content="USD">
<meta property="og:availability" content="instock">
<meta property="og:image" content="/images/fallback.jpg">
</head>
<body></body>
</html>
"""

VISIBLE_TEXT_ONLY_PAGE = """
<html>
<body>
<h1>Pokémon Center Mystery Item</h1>
<p>Price: $24.99</p>
<p>Add to Cart</p>
</body>
</html>
"""

BLOCKED_PAGE = """
<html><body>
Pardon Our Interruption
<div id="_Incapsula_Resource">...</div>
</body></html>
"""

# Trimmed down, structurally faithful copy of the real
# Incapsula/Imperva interruption page returned by
# pokemoncenter.com/category/trading-card-game in production (fetched
# and inspected live during diagnosis; only third-party incident IDs
# were removed).
REAL_INCAPSULA_INTERSTITIAL_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <noscript>
        <title>Pardon Our Interruption</title>
    </noscript>
    <meta name="robots" content="noindex, nofollow">
</head>
<body>
<div class="container">
    <h1>Pardon Our Interruption</h1>
    <p>As you were browsing something about your browser made us
    think you were a bot.</p>
</div>
</body>
</html>
"""

# Trimmed down, structurally faithful copy of a REAL, legitimate
# pokemon.com product-gallery page (fetched and inspected live during
# diagnosis). It is genuinely real content - og:title, og:image, and
# real product description text - but it also routinely loads an
# async Incapsula bot-fingerprinting script and a reCAPTCHA Enterprise
# script as normal, always-on site infrastructure, unrelated to
# whether this specific request was blocked. Proves the false
# positive that caused every pokemon.com gallery page to be
# misclassified as BLOCKED before this fix.
REAL_LEGITIMATE_GALLERY_PAGE_WITH_ROUTINE_SECURITY_SCRIPTS = """
<html>
<head>
    <script src="https://www.recaptcha.net/recaptcha/enterprise.js?render=abc123"></script>
    <meta property="og:title" content="Pokémon TCG: Mega Evolution—Pitch Black Elite Trainer Box">
    <meta property="og:image" content="/static-assets/content-assets/me05-etb.png">
</head>
<body>
<h1>Pokémon TCG: Mega Evolution—Pitch Black Elite Trainer Box</h1>
<p>Launch: July 17, 2026. Twinkling city lights and a starry sky
become obscured in darkness as Mega Darkrai ex arrives.</p>
<script type="text/javascript" src="/_Incapsula_Resource?SWJIYLWA=abc123&ns=3" async></script>
</body>
</html>
"""

GALLERY_PAGE_SINGLE_MAPPING = """
<html><body>
<h1>Mega Dragonite ex Elite Trainer Box</h1>
<a href="/us/privacy">Privacy</a>
<a href="https://www.pokemoncenter.com/product/12345-dragonite-etb">Shop Now</a>
</body></html>
"""

GALLERY_PAGE_AMBIGUOUS_MAPPING = """
<html><body>
<a href="https://www.pokemoncenter.com/product/item-a">Item A</a>
<a href="https://www.pokemoncenter.com/product/item-b">Item B</a>
</body></html>
"""

GALLERY_PAGE_NO_MAPPING = """
<html><body>
<p>No commerce links here.</p>
<a href="/us/pokemon-news/some-article">Read more</a>
</body></html>
"""


def base_item(url="https://www.pokemoncenter.com/product/12345-dragonite-etb"):
    return {
        "title": "Mega Dragonite ex Elite Trainer Box",
        "url": url,
        "sku": None,
        "retail_price": None,
        "availability": None,
    }


def test_structured_page_extracts_price_stock_sku_image_and_limit():
    retriever = FakeRetriever({
        base_item()["url"]: STRUCTURED_PRODUCT_PAGE,
    })

    item = base_item()

    result = collect_pokemon_product_detail(
        item,
        retriever=retriever,
    )

    assert result["retail_price"] == 59.99
    assert result["currency"] == "USD"
    assert result["availability"] == "InStock"
    assert result["sku"] == "PC-ETB-DRAGONITE"
    assert result["product_id"] == "PC-ETB-DRAGONITE"
    assert result["image_url"] == (
        "https://www.pokemoncenter.com/"
        "images/dragonite-etb.jpg"
    )
    assert result["purchase_limit"] == 2
    assert result["detail_source"] == "structured_data"
    assert result["source_timestamp"] is not None


def test_out_of_stock_page_normalizes_to_outofstock():
    url = "https://www.pokemoncenter.com/product/booster-bundle"

    retriever = FakeRetriever({
        url: OUT_OF_STOCK_PAGE,
    })

    result = collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    assert result["availability"] == "OutOfStock"
    assert result["preorder_status"] is False


def test_preorder_page_normalizes_to_preorder():
    url = "https://www.pokemoncenter.com/product/collection-box"

    retriever = FakeRetriever({
        url: PREORDER_PAGE,
    })

    result = collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    assert result["availability"] == "PreOrder"
    assert result["preorder_status"] is True


def test_coming_soon_text_only_page_normalizes_to_comingsoon_not_instock():
    url = "https://www.pokemoncenter.com/product/coming-soon-item"

    retriever = FakeRetriever({
        url: COMING_SOON_TEXT_ONLY_PAGE,
    })

    result = collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    assert result["availability"] == "ComingSoon"

    # Critical: must not be misread as purchasable just because a
    # real page exists.
    assert result["availability"] != "InStock"


def test_malformed_structured_data_falls_back_to_meta_tags():
    url = "https://www.pokemoncenter.com/product/fallback-item"

    retriever = FakeRetriever({
        url: MALFORMED_STRUCTURED_DATA_PAGE,
    })

    result = collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    assert result["retail_price"] == 49.99
    assert result["currency"] == "USD"
    assert result["availability"] == "InStock"
    assert result["detail_source"] == "meta_tags"


def test_visible_text_is_the_last_resort_fallback():
    url = "https://www.pokemoncenter.com/product/mystery-item"

    retriever = FakeRetriever({
        url: VISIBLE_TEXT_ONLY_PAGE,
    })

    result = collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    assert result["retail_price"] == 24.99
    assert result["availability"] == "InStock"
    assert result["detail_source"] == "visible_text"


def test_request_failure_preserves_original_item():
    url = "https://www.pokemoncenter.com/product/network-blip"

    retriever = FakeRetriever({
        url: ConnectionError("network unreachable"),
    })

    original = {
        "title": "Existing Known Item",
        "url": url,
        "sku": "ALREADY-KNOWN-SKU",
        "retail_price": 19.99,
        "availability": "InStock",
    }

    result = collect_pokemon_product_detail(
        original,
        retriever=retriever,
    )

    assert result["sku"] == "ALREADY-KNOWN-SKU"
    assert result["retail_price"] == 19.99
    assert result["availability"] == "InStock"
    assert result["detail_source"] == "fetch_failed"


def test_blocked_page_preserves_original_item_and_is_logged(capsys):
    url = "https://www.pokemoncenter.com/product/blocked-item"

    retriever = FakeRetriever({
        url: BLOCKED_PAGE,
    })

    original = {
        "title": "Blocked Item",
        "url": url,
        "sku": "PRE-EXISTING",
        "retail_price": None,
        "availability": None,
    }

    result = collect_pokemon_product_detail(
        original,
        retriever=retriever,
    )

    assert result["sku"] == "PRE-EXISTING"
    assert result["detail_source"] == "blocked"

    captured = capsys.readouterr()
    assert (
        "[PokemonDetailCollector]" in captured.out
    )
    assert "blocked" in captured.out.lower()


def test_gallery_url_with_unambiguous_commerce_mapping_is_resolved():
    gallery_url = (
        "https://www.pokemon.com/us/pokemon-tcg/"
        "product-gallery/dragonite-etb"
    )
    commerce_url = (
        "https://www.pokemoncenter.com/"
        "product/12345-dragonite-etb"
    )

    retriever = FakeRetriever({
        gallery_url: GALLERY_PAGE_SINGLE_MAPPING,
        commerce_url: STRUCTURED_PRODUCT_PAGE,
    })

    result = collect_pokemon_product_detail(
        base_item(gallery_url),
        retriever=retriever,
    )

    assert result["url"] == commerce_url
    assert result["discovery_url"] == gallery_url
    assert result["retail_price"] == 59.99
    assert (
        "mapped_from_gallery"
        in result["detail_source"]
    )


def test_ambiguous_gallery_page_is_not_mapped():
    gallery_url = (
        "https://www.pokemon.com/us/pokemon-tcg/"
        "product-gallery/some-listing"
    )

    retriever = FakeRetriever({
        gallery_url: GALLERY_PAGE_AMBIGUOUS_MAPPING,
    })

    result = collect_pokemon_product_detail(
        base_item(gallery_url),
        retriever=retriever,
    )

    # No guessed mapping: url must remain the original gallery url.
    assert result["url"] == gallery_url
    assert result["discovery_url"] == gallery_url
    assert "mapped_from_gallery" not in (
        result["detail_source"] or ""
    )


def test_gallery_page_with_no_commerce_link_is_not_mapped():
    gallery_url = (
        "https://www.pokemon.com/us/pokemon-news/"
        "some-article"
    )

    retriever = FakeRetriever({
        gallery_url: GALLERY_PAGE_NO_MAPPING,
    })

    result = collect_pokemon_product_detail(
        base_item(gallery_url),
        retriever=retriever,
    )

    assert result["url"] == gallery_url


def test_resolve_commerce_url_helper_directly_requires_exactly_one_match():
    resolved = resolve_commerce_url_from_gallery_html(
        GALLERY_PAGE_SINGLE_MAPPING,
        base_url="https://www.pokemon.com",
    )

    assert resolved == (
        "https://www.pokemoncenter.com/"
        "product/12345-dragonite-etb"
    )

    assert (
        resolve_commerce_url_from_gallery_html(
            GALLERY_PAGE_AMBIGUOUS_MAPPING,
            base_url="https://www.pokemon.com",
        )
        is None
    )

    assert (
        resolve_commerce_url_from_gallery_html(
            GALLERY_PAGE_NO_MAPPING,
            base_url="https://www.pokemon.com",
        )
        is None
    )


def test_normalize_price_handles_common_formats():
    assert normalize_price("$59.99") == 59.99
    assert normalize_price("1,299.00") == 1299.00
    assert normalize_price(59.99) == 59.99
    assert normalize_price(None) is None
    assert normalize_price("not a price") is None


def test_normalize_availability_maps_full_vocabulary():
    assert normalize_availability("InStock") == "InStock"
    assert (
        normalize_availability(
            "https://schema.org/OutOfStock"
        )
        == "OutOfStock"
    )
    assert normalize_availability("PreOrder") == "PreOrder"
    assert (
        normalize_availability("Discontinued")
        == "Unavailable"
    )
    assert normalize_availability(None) == "Unknown"
    assert (
        normalize_availability("SomethingWeird")
        == "Unknown"
    )


def test_normalize_availability_is_compatible_with_state_tracker_vocabulary():
    """
    state_tracker.py's own normalization lowercases and strips
    separators before checking membership in its known available/
    unavailable sets. Every non-Unknown value this module produces
    must survive that normalization into a value state_tracker.py
    actually recognizes, and Unknown/ComingSoon must land outside
    both sets so they never produce a false RESTOCK/SOLD_OUT signal.
    """
    from scouts.pokemon.state_tracker import (
        PokemonStateTracker,
    )

    def state_tracker_normalize(value):
        return (
            str(value or "")
            .strip()
            .lower()
            .replace("_", "")
            .replace("-", "")
            .replace(" ", "")
        )

    known_available = {
        "instock",
        "available",
        "preorder",
        "preorderonly",
    }
    known_unavailable = {
        "soldout",
        "outofstock",
        "unavailable",
        "discontinued",
    }

    assert (
        state_tracker_normalize(
            normalize_availability("InStock")
        )
        in known_available
    )
    assert (
        state_tracker_normalize(
            normalize_availability(
                "https://schema.org/OutOfStock"
            )
        )
        in known_unavailable
    )
    assert (
        state_tracker_normalize(
            normalize_availability("PreOrder")
        )
        in known_available
    )
    assert (
        state_tracker_normalize(
            normalize_availability("Discontinued")
        )
        in known_unavailable
    )

    coming_soon_normalized = state_tracker_normalize(
        normalize_availability("ComingSoon")
    )
    assert coming_soon_normalized not in known_available
    assert coming_soon_normalized not in known_unavailable

    unknown_normalized = state_tracker_normalize(
        normalize_availability(None)
    )
    assert unknown_normalized not in known_available
    assert unknown_normalized not in known_unavailable


def test_completeness_recalculates_after_detail_enrichment():
    from scouts.pokemon.product_details import (
        extract_product_details,
    )

    url = base_item()["url"]

    before = extract_product_details(
        base_item(url)
    )

    retriever = FakeRetriever({
        url: STRUCTURED_PRODUCT_PAGE,
    })

    enriched_item = collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    after = extract_product_details(
        enriched_item
    )

    assert (
        after["detail_completeness_score"]
        > before["detail_completeness_score"]
    )
    assert (
        len(after["missing_detail_fields"])
        < len(before["missing_detail_fields"])
    )
    assert "retail_price" not in after[
        "missing_detail_fields"
    ]
    assert "sku" not in after[
        "missing_detail_fields"
    ]


def test_non_dict_item_is_returned_unchanged():
    result = collect_pokemon_product_detail(
        "not-a-dict",
        retriever=FakeRetriever({}),
    )

    assert result == "not-a-dict"


def test_item_with_no_url_is_stamped_and_preserved():
    item = {"title": "No URL Item"}

    result = collect_pokemon_product_detail(
        item,
        retriever=FakeRetriever({}),
    )

    assert result["title"] == "No URL Item"
    assert result["detail_source"] == "no_url"
    assert result["availability"] == "Unknown"


def test_classify_detail_content_distinguishes_blocked_empty_and_ok():
    assert classify_detail_content(None) == "EMPTY"
    assert classify_detail_content("   ") == "EMPTY"
    assert (
        classify_detail_content(BLOCKED_PAGE)
        == "BLOCKED"
    )
    assert (
        classify_detail_content(
            STRUCTURED_PRODUCT_PAGE
        )
        == "OK"
    )


def test_real_incapsula_interstitial_page_is_still_detected_as_blocked():
    assert (
        classify_detail_content(
            REAL_INCAPSULA_INTERSTITIAL_PAGE
        )
        == "BLOCKED"
    )


def test_legitimate_page_with_routine_security_scripts_is_not_misclassified_as_blocked():
    """
    Regression test for the production root cause: pokemon.com pages
    routinely load an async Incapsula bot-fingerprinting script and a
    reCAPTCHA Enterprise script as normal site infrastructure on every
    page, blocked or not. A marker list that treats the mere presence
    of "incapsula" or "captcha" anywhere in the HTML as proof of
    blocking misclassifies every real page as blocked, which is
    exactly what silently prevented any enrichment in production.
    """
    assert (
        classify_detail_content(
            REAL_LEGITIMATE_GALLERY_PAGE_WITH_ROUTINE_SECURITY_SCRIPTS
        )
        == "OK"
    )


def test_legitimate_gallery_page_now_yields_meta_tag_enrichment(
    capsys,
):
    """
    The real gallery page has og:image only in meta tags and a
    release date only in visible body text, with routine Incapsula/
    reCAPTCHA scripts that must not trigger block detection. Both the
    absolute image URL (meta tier) and the normalized release date
    (visible-text tier) must end up in the final result - finding
    image_url via meta tags must not stop the visible-text tier from
    also being searched.
    """
    url = (
        "https://www.pokemon.com/us/pokemon-tcg/"
        "product-gallery/me05-etb"
    )

    retriever = FakeRetriever({
        url: (
            REAL_LEGITIMATE_GALLERY_PAGE_WITH_ROUTINE_SECURITY_SCRIPTS
        ),
    })

    result = collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    # Strongest contributing tier is reported as detail_source...
    assert result["detail_source"] == "meta_tags"

    # ...but both tiers' fields are present in the combined result.
    assert result["detail_sources"] == [
        "meta_tags",
        "visible_text",
    ]

    assert result["image_url"] == (
        "https://www.pokemon.com/"
        "static-assets/content-assets/"
        "me05-etb.png"
    )
    assert result["release_date"] == "2026-07-17"

    captured = capsys.readouterr()
    assert "blocked=False" in captured.out
    assert "source=meta_tags+visible_text" in (
        captured.out
    )
    assert "image_url" in captured.out
    assert "release_date" in captured.out


def test_visible_text_value_does_not_overwrite_structured_data_value():
    """
    STRUCTURED_PRODUCT_PAGE's JSON-LD provides retail_price=59.99 and
    availability=InStock. Its body also happens to contain
    "Limit 2 per customer" text, which is a genuinely text-only
    signal, but if the page's visible text also contained a
    conflicting price/availability term, the structured-data value
    must win - a weaker tier must never overwrite a stronger tier's
    already-populated value.
    """
    conflicting_text_page = (
        STRUCTURED_PRODUCT_PAGE.replace(
            "<p>Limit 2 per customer.</p>",
            "<p>Limit 2 per customer. "
            "Was $19.99, now Sold Out "
            "everywhere.</p>",
        )
    )

    result = collect_pokemon_product_detail(
        base_item(),
        retriever=FakeRetriever({
            base_item()["url"]: (
                conflicting_text_page
            ),
        }),
    )

    # Structured data's real values must survive, not the visible
    # text's conflicting "$19.99" / "Sold Out" mentions.
    assert result["retail_price"] == 59.99
    assert result["availability"] == "InStock"
    assert result["detail_source"] == (
        "structured_data"
    )


def test_fields_from_all_applicable_tiers_are_combined():
    """
    A page with JSON-LD providing only sku+availability, meta tags
    providing only image_url, and visible text providing only
    release_date and purchase_limit - all four must end up in the
    final combined result, and detail_sources must list every tier
    that actually contributed something.
    """
    combined_page = """
    <html><head>
    <script type="application/ld+json">
    {
        "@type": "Product",
        "name": "Combined Tier Test Item",
        "sku": "COMBINED-SKU-1",
        "offers": {"availability": "https://schema.org/InStock"}
    }
    </script>
    <meta property="og:image" content="/images/combined.jpg">
    </head><body>
    <p>Launch: August 3, 2026. Limit 1 per customer.</p>
    </body></html>
    """

    url = "https://www.pokemoncenter.com/product/combined"

    result = collect_pokemon_product_detail(
        base_item(url),
        retriever=FakeRetriever({
            url: combined_page,
        }),
    )

    assert result["sku"] == "COMBINED-SKU-1"
    assert result["availability"] == "InStock"
    assert result["image_url"] == (
        "https://www.pokemoncenter.com/"
        "images/combined.jpg"
    )
    assert result["release_date"] == "2026-08-03"
    assert result["purchase_limit"] == 1

    assert result["detail_sources"] == [
        "structured_data",
        "meta_tags",
        "visible_text",
    ]
    assert result["detail_source"] == (
        "structured_data"
    )


def test_diagnostic_populated_fields_reflect_the_combined_result(
    capsys,
):
    combined_page = """
    <html><head>
    <script type="application/ld+json">
    {
        "@type": "Product",
        "name": "Diagnostic Combined Item",
        "sku": "DIAG-SKU-1"
    }
    </script>
    <meta property="og:image" content="/images/diag.jpg">
    </head><body>
    <p>Launch: September 9, 2026.</p>
    </body></html>
    """

    url = "https://www.pokemoncenter.com/product/diag-combined"

    collect_pokemon_product_detail(
        base_item(url),
        retriever=FakeRetriever({
            url: combined_page,
        }),
    )

    captured = capsys.readouterr()
    line = captured.out.strip()

    assert "sku" in line
    assert "image_url" in line
    assert "release_date" in line
    assert "reason=enriched" in line


def test_find_commerce_links_returns_every_match():
    links = find_commerce_links(
        GALLERY_PAGE_AMBIGUOUS_MAPPING,
        base_url="https://www.pokemon.com",
    )

    assert len(links) == 2


def test_extract_detail_fields_prefers_structured_over_meta_and_text():
    fields = extract_detail_fields(
        STRUCTURED_PRODUCT_PAGE,
        base_item()["url"],
    )

    assert fields["detail_source"] == "structured_data"

    fallback_fields = extract_detail_fields(
        MALFORMED_STRUCTURED_DATA_PAGE,
        "https://www.pokemoncenter.com/product/x",
    )

    assert (
        fallback_fields["detail_source"]
        == "meta_tags"
    )


def test_diagnostic_line_reports_success_with_populated_fields(
    capsys,
):
    retriever = FakeRetriever({
        base_item()["url"]: STRUCTURED_PRODUCT_PAGE,
    })

    collect_pokemon_product_detail(
        base_item(),
        retriever=retriever,
    )

    captured = capsys.readouterr()
    line = captured.out.strip()

    assert line.startswith(
        "[PokemonDetailCollector] diagnostic "
    )
    assert f"url={base_item()['url']}" in line
    assert "fetch=ok" in line
    assert "blocked=False" in line
    assert "source=structured_data" in line
    assert "retail_price" in line
    assert "reason=enriched" in line


def test_diagnostic_line_reports_no_url_case(capsys):
    collect_pokemon_product_detail(
        {"title": "No URL Item"},
        retriever=FakeRetriever({}),
    )

    captured = capsys.readouterr()
    line = captured.out.strip()

    assert "url=None" in line
    assert "fetch=skipped" in line
    assert "reason=item_has_no_url" in line


def test_diagnostic_line_reports_fetch_error_without_exposing_secrets(
    capsys,
):
    url = "https://www.pokemoncenter.com/product/x"

    retriever = FakeRetriever({
        url: ConnectionError(
            "network unreachable"
        ),
    })

    collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    captured = capsys.readouterr()
    line = captured.out.strip()

    assert "fetch=error" in line
    assert "reason=ConnectionError" in line

    # No cookies, headers, or credential-shaped values in any log
    # line this call produced.
    forbidden_substrings = [
        "cookie",
        "authorization",
        "apikey",
        "api_key",
        "bearer",
        "set-cookie",
    ]
    lowered_output = captured.out.lower()
    for forbidden in forbidden_substrings:
        assert forbidden not in lowered_output


def test_diagnostic_line_reports_blocked_case_with_matched_marker(
    capsys,
):
    url = "https://www.pokemoncenter.com/product/blocked"

    retriever = FakeRetriever({
        url: REAL_INCAPSULA_INTERSTITIAL_PAGE,
    })

    collect_pokemon_product_detail(
        base_item(url),
        retriever=retriever,
    )

    captured = capsys.readouterr()
    line = captured.out.strip()

    assert "blocked=True" in line
    assert (
        "reason=block_marker_matched:"
        "pardon our interruption" in line
    )


def test_diagnostic_line_reports_commerce_link_count_and_mapped_url(
    capsys,
):
    gallery_url = (
        "https://www.pokemon.com/us/pokemon-tcg/"
        "product-gallery/dragonite-etb"
    )
    commerce_url = (
        "https://www.pokemoncenter.com/"
        "product/12345-dragonite-etb"
    )

    retriever = FakeRetriever({
        gallery_url: GALLERY_PAGE_SINGLE_MAPPING,
        commerce_url: STRUCTURED_PRODUCT_PAGE,
    })

    collect_pokemon_product_detail(
        base_item(gallery_url),
        retriever=retriever,
    )

    captured = capsys.readouterr()
    line = captured.out.strip()

    assert "commerce_links=1" in line
    assert f"mapped_url={commerce_url}" in line


def test_diagnostic_line_is_a_single_concise_line_per_call(capsys):
    retriever = FakeRetriever({
        base_item()["url"]: STRUCTURED_PRODUCT_PAGE,
    })

    collect_pokemon_product_detail(
        base_item(),
        retriever=retriever,
    )

    captured = capsys.readouterr()
    diagnostic_lines = [
        line
        for line in captured.out.splitlines()
        if line.startswith(
            "[PokemonDetailCollector] diagnostic"
        )
    ]

    assert len(diagnostic_lines) == 1
