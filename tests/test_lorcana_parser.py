from scouts.lorcana.parser import (
    parse_lorcana_item,
)


def test_lorcana_parser_creates_item():
    item = parse_lorcana_item(
        title=(
            "Disney Lorcana "
            "D23 Collector Gift Set"
        ),
        url=(
            "https://www.disneylorcana.com/"
            "en-US/product/test"
        ),
        description=(
            "Limited collection with "
            "exclusive promo cards."
        ),
    )

    assert (
        item["brand"]
        == "Disney Lorcana"
    )

    assert (
        item["category"]
        == "lorcana"
    )

    assert (
        item["tcg_name"]
        == "lorcana"
    )

    assert "D23" in (
        item["product_codes"]
    )