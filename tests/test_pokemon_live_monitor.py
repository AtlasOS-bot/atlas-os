from scouts.pokemon.live_monitor import (
    PokemonLiveMonitor,
)


def test_live_monitor_saves_current_and_history(
    tmp_path,
):
    current_path = (
        tmp_path
        / "pokemon_live_scan.json"
    )

    history_directory = (
        tmp_path
        / "history"
    )

    raw_items = [
        {
            "title": (
                "Pokémon Center "
                "Anniversary Elite Trainer Box"
            ),
            "url": (
                "https://www.pokemoncenter.com/"
                "product/test-etb"
            ),
            "sku": "PKM-LIVE-001",
            "availability": "InStock",
            "retail_price": 59.99,
            "currency": "USD",
        }
    ]

    def fake_collector():
        return raw_items

    def fake_enricher(item):
        return {
            **item,
            "category": "pokemon",
            "product_type": (
                "elite_trainer_box"
            ),
            "pokemon_center_exclusive": True,
            "collector_score": 92,
            "popularity_score": 90,
            "flip_score": 88,
            "hold_score": 95,
            "sleeper_score": 30,
            "best_strategy": {
                "strategy": (
                    "LONG-TERM HOLD"
                ),
                "score": 95,
            },
        }

    monitor = PokemonLiveMonitor(
        scan_path=current_path,
        history_directory=(
            history_directory
        ),
        collector=fake_collector,
        enricher=fake_enricher,
    )

    snapshot = monitor.scan()

    assert (
        snapshot["status"]
        == "SUCCESS"
    )

    assert (
        snapshot["product_count"]
        == 1
    )

    assert (
        snapshot["summary"][
            "in_stock_count"
        ]
        == 1
    )

    assert (
        snapshot["summary"][
            "exclusive_count"
        ]
        == 1
    )

    assert (
        current_path.exists()
        is True
    )

    history_files = list(
        history_directory.glob(
            "*.json"
        )
    )

    assert len(history_files) == 1


def test_live_monitor_deduplicates_products(
    tmp_path,
):
    raw_items = [
        {
            "title": "Test Pokémon ETB",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/test-etb"
            ),
            "availability": "InStock",
            "description": "Short",
            "sources": [
                "pokemon_center_tcg",
            ],
        },
        {
            "title": "Test Pokémon ETB",
            "url": (
                "https://www.pokemoncenter.com/"
                "product/test-etb"
            ),
            "availability": "InStock",
            "description": (
                "Longer official product "
                "description."
            ),
            "sources": [
                "pokemon_center_new_releases",
            ],
        },
    ]

    def fake_collector():
        return raw_items

    def fake_enricher(item):
        return {
            **item,
            "category": "pokemon",
            "collector_score": 50,
            "flip_score": 45,
            "hold_score": 55,
            "popularity_score": 40,
        }

    monitor = PokemonLiveMonitor(
        scan_path=(
            tmp_path
            / "latest.json"
        ),
        history_directory=(
            tmp_path
            / "history"
        ),
        collector=fake_collector,
        enricher=fake_enricher,
    )

    snapshot = monitor.scan()

    assert (
        snapshot["product_count"]
        == 1
    )

    product = snapshot[
        "items"
    ][0]

    assert set(
        product["sources"]
    ) == {
        "pokemon_center_tcg",
        "pokemon_center_new_releases",
    }

    assert (
        product["description"]
        == (
            "Longer official product "
            "description."
        )
    )


def test_live_monitor_handles_collection_failure(
    tmp_path,
):
    def failing_collector():
        raise ConnectionError(
            "Temporary source failure"
        )

    monitor = PokemonLiveMonitor(
        scan_path=(
            tmp_path
            / "latest.json"
        ),
        history_directory=(
            tmp_path
            / "history"
        ),
        collector=(
            failing_collector
        ),
        enricher=lambda item: item,
    )

    snapshot = monitor.scan()

    assert (
        snapshot["status"]
        == "FAILED"
    )

    assert (
        snapshot["product_count"]
        == 0
    )

    assert (
        snapshot["error_count"]
        == 1
    )

    assert (
        snapshot["errors"][0][
            "stage"
        ]
        == "collection"
    )


def test_live_monitor_ranks_available_product_first(
    tmp_path,
):
    raw_items = [
        {
            "title": "Sold Out Product",
            "url": (
                "https://example.com/"
                "sold-out"
            ),
            "availability": (
                "OutOfStock"
            ),
            "collector_score": 95,
        },
        {
            "title": "Available Product",
            "url": (
                "https://example.com/"
                "available"
            ),
            "availability": "InStock",
            "collector_score": 75,
        },
    ]

    monitor = PokemonLiveMonitor(
        scan_path=(
            tmp_path
            / "latest.json"
        ),
        history_directory=(
            tmp_path
            / "history"
        ),
        collector=lambda: raw_items,
        enricher=lambda item: {
            **item,
            "category": "pokemon",
            "flip_score": 60,
            "hold_score": 70,
            "popularity_score": 65,
        },
    )

    snapshot = monitor.scan()

    assert (
        snapshot["items"][0][
            "title"
        ]
        == "Available Product"
    )