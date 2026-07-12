from scouts.pokemon.identity import (
    canonical_product_key,
    identity_similarity,
    same_product,
)


def test_similar_product_titles_match():
    first = {
        "title": (
            "Pokémon TCG Mega Evolution "
            "Ascended Heroes Booster Bundle"
        ),
    }

    second = {
        "title": (
            "Mega Evolution Ascended Heroes "
            "6-Pack Booster Bundle"
        ),
    }

    assert (
        identity_similarity(
            first,
            second,
        )
        >= 0.72
    )

    assert same_product(
        first,
        second,
    ) is True


def test_unrelated_products_do_not_match():
    first = {
        "title": (
            "Ascended Heroes Booster Bundle"
        ),
    }

    second = {
        "title": "Pikachu Poké Plush",
    }

    assert same_product(
        first,
        second,
    ) is False


def test_sku_creates_stable_identity():
    item = {
        "title": "Different Product Name",
        "sku": "ABC-123",
    }

    assert (
        canonical_product_key(item)
        == "sku:abc-123"
    )