from scouts.pokemon.detail_collector import (
    classify_detail_content,
    collect_pokemon_product_detail,
    extract_detail_fields,
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
