from scouts.one_piece.parser import (
    extract_product_codes,
    parse_one_piece_item,
)


def test_one_piece_parser_creates_item():
    item = parse_one_piece_item(
        title=(
            "BOOSTER PACK "
            "-ADVENTURE ON KAMI'S ISLAND- "
            "[OP15-EB04]"
        ),
        url=(
            "https://en.onepiece-cardgame.com/"
            "products/boosters/op15.php"
        ),
        description=(
            "Official One Piece Card Game "
            "booster product."
        ),
    )

    assert (
        item["brand"]
        == "One Piece Card Game"
    )

    assert (
        item["category"]
        == "one_piece"
    )

    assert (
        item["tcg_name"]
        == "one_piece"
    )

    assert "OP-15" in item[
        "product_codes"
    ]

    assert "EB-04" in item[
        "product_codes"
    ]

    assert (
        item["primary_set_code"]
        == "OP-15"
    )


def test_one_piece_code_normalization():
    codes = extract_product_codes(
        (
            "Starter Deck ST29 "
            "with promo P-084 "
            "and booster OP 13"
        )
    )

    assert "ST-29" in codes
    assert "P-084" in codes
    assert "OP-13" in codes