import importlib

import memory.nike_memory as nike_memory_module
import memory.pokemon_memory as pokemon_memory_module


class FakeResponse:

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_pokemon_memory_module_imports_without_supabase_env(
    monkeypatch,
):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    importlib.reload(pokemon_memory_module)


def test_nike_memory_module_imports_without_supabase_env(
    monkeypatch,
):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    importlib.reload(nike_memory_module)


def test_pokemon_memory_is_safe_no_op_without_credentials(
    monkeypatch,
):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "requests.get should not be called "
            "without Supabase credentials"
        )

    monkeypatch.setattr(
        pokemon_memory_module.requests,
        "get",
        fail_if_called,
    )

    memory = pokemon_memory_module.pokemon_memory()

    assert memory == {
        "total_items_seen": 0,
        "promo_count": 0,
        "exclusive_count": 0,
        "watch_count": 0,
        "buy_count": 0,
    }


def test_nike_memory_is_safe_no_op_without_credentials(
    monkeypatch,
):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "requests.get should not be called "
            "without Supabase credentials"
        )

    monkeypatch.setattr(
        nike_memory_module.requests,
        "get",
        fail_if_called,
    )

    memory = nike_memory_module.nike_memory()

    assert memory == {
        "total_items_seen": 0,
        "hype_drop_count": 0,
        "restock_count": 0,
        "collab_count": 0,
    }


def test_pokemon_memory_fetches_and_summarizes_with_credentials(
    monkeypatch,
):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

    captured = {}

    def fake_get(url, headers, params):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params

        return FakeResponse([
            {
                "atlas_reason": "Promo card included, exclusive release.",
                "recommended_action": "BUY",
            },
            {
                "atlas_reason": "Standard release.",
                "recommended_action": "WATCH",
            },
        ])

    monkeypatch.setattr(
        pokemon_memory_module.requests,
        "get",
        fake_get,
    )

    memory = pokemon_memory_module.pokemon_memory()

    assert memory == {
        "total_items_seen": 2,
        "promo_count": 1,
        "exclusive_count": 1,
        "watch_count": 1,
        "buy_count": 1,
    }

    assert captured["url"] == (
        "https://example.supabase.co/rest/v1/opportunities"
    )
    assert captured["headers"]["apikey"] == "test-service-key"
    assert (
        captured["headers"]["Authorization"]
        == "Bearer test-service-key"
    )


def test_nike_memory_fetches_and_summarizes_with_credentials(
    monkeypatch,
):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

    captured = {}

    def fake_get(url, headers, params):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params

        return FakeResponse([
            {
                "item_name": "Travis Scott Jordan 1",
                "atlas_reason": "Collab shock drop expected.",
            },
            {
                "item_name": "Pegasus restock",
                "atlas_reason": "Restock detected.",
            },
        ])

    monkeypatch.setattr(
        nike_memory_module.requests,
        "get",
        fake_get,
    )

    memory = nike_memory_module.nike_memory()

    assert memory == {
        "total_items_seen": 2,
        "hype_drop_count": 1,
        "restock_count": 1,
        "collab_count": 1,
    }

    assert captured["url"] == (
        "https://example.supabase.co/rest/v1/opportunities"
    )
    assert captured["headers"]["apikey"] == "test-service-key"


def test_recent_pokemon_items_returns_empty_list_without_credentials(
    monkeypatch,
):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    assert pokemon_memory_module.recent_pokemon_items() == []
