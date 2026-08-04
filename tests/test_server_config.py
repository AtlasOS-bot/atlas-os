"""
Atlas web server - config loading tests, focused on the production
origin requirement: ATLAS_PUBLIC_ORIGIN must be present and
well-formed in production, or the app refuses to start.
"""

import pytest

from server.config import ConfigError, load_config_from_env

BASE_ENV = {
    "ATLAS_PASSWORD_HASH": "pbkdf2_sha256$1000$abc$def",
    "ATLAS_SESSION_SECRET": "test-secret",
    "SUPABASE_URL": "https://example.test",
    "SUPABASE_SERVICE_KEY": "fake-key",
}


def env(**overrides):
    merged = dict(BASE_ENV)
    merged.update(overrides)
    return merged


class TestProductionRequiresOrigin:
    def test_missing_origin_fails_closed(self):
        with pytest.raises(ConfigError, match="ATLAS_PUBLIC_ORIGIN is required"):
            load_config_from_env(env())  # no ATLAS_ENV -> defaults to production

    def test_explicit_production_missing_origin_fails_closed(self):
        with pytest.raises(ConfigError, match="ATLAS_PUBLIC_ORIGIN is required"):
            load_config_from_env(env(ATLAS_ENV="production"))

    def test_valid_https_origin_accepted(self):
        config = load_config_from_env(env(ATLAS_PUBLIC_ORIGIN="https://atlas.example.com"))
        assert config.public_origin == "https://atlas.example.com"
        assert config.environment == "production"

    def test_trailing_slash_normalized(self):
        config = load_config_from_env(env(ATLAS_PUBLIC_ORIGIN="https://atlas.example.com/"))
        assert config.public_origin == "https://atlas.example.com"

    def test_http_origin_rejected_in_production(self):
        with pytest.raises(ConfigError, match="not a valid"):
            load_config_from_env(env(ATLAS_PUBLIC_ORIGIN="http://atlas.example.com"))

    def test_localhost_origin_rejected_in_production(self):
        with pytest.raises(ConfigError, match="not a valid"):
            load_config_from_env(env(ATLAS_PUBLIC_ORIGIN="http://localhost:3000"))

    def test_wildcard_origin_rejected(self):
        with pytest.raises(ConfigError, match="not a valid"):
            load_config_from_env(env(ATLAS_PUBLIC_ORIGIN="https://*.example.com"))

    def test_origin_with_path_rejected(self):
        with pytest.raises(ConfigError, match="not a valid"):
            load_config_from_env(env(ATLAS_PUBLIC_ORIGIN="https://atlas.example.com/some/path"))


class TestDevelopmentMode:
    def test_development_mode_does_not_require_origin(self):
        config = load_config_from_env(env(ATLAS_ENV="development"))
        assert config.environment == "development"
        assert config.public_origin is None

    def test_development_mode_accepts_localhost_origin(self):
        config = load_config_from_env(env(ATLAS_ENV="development", ATLAS_PUBLIC_ORIGIN="http://localhost:3000"))
        assert config.public_origin == "http://localhost:3000"

    def test_development_mode_still_rejects_malformed_origin(self):
        with pytest.raises(ConfigError, match="not a valid"):
            load_config_from_env(env(ATLAS_ENV="development", ATLAS_PUBLIC_ORIGIN="https://*.example.com"))

    def test_development_mode_rejects_non_localhost_http(self):
        with pytest.raises(ConfigError, match="not a valid"):
            load_config_from_env(env(ATLAS_ENV="development", ATLAS_PUBLIC_ORIGIN="http://example.com"))


class TestInvalidEnvironmentValue:
    def test_unknown_environment_value_rejected(self):
        with pytest.raises(ConfigError, match="ATLAS_ENV"):
            load_config_from_env(env(ATLAS_ENV="staging"))


class TestTrustVercelIpHeaders:
    def test_true_in_production(self):
        config = load_config_from_env(env(ATLAS_PUBLIC_ORIGIN="https://atlas.example.com"))
        assert config.trust_vercel_ip_headers is True

    def test_false_in_development(self):
        config = load_config_from_env(env(ATLAS_ENV="development"))
        assert config.trust_vercel_ip_headers is False


class TestMissingRequiredVars:
    def test_missing_password_hash(self):
        bad_env = env(ATLAS_PUBLIC_ORIGIN="https://atlas.example.com")
        del bad_env["ATLAS_PASSWORD_HASH"]
        with pytest.raises(ConfigError, match="ATLAS_PASSWORD_HASH"):
            load_config_from_env(bad_env)

    def test_missing_supabase_service_key(self):
        bad_env = env(ATLAS_PUBLIC_ORIGIN="https://atlas.example.com")
        del bad_env["SUPABASE_SERVICE_KEY"]
        with pytest.raises(ConfigError, match="SUPABASE_SERVICE_KEY"):
            load_config_from_env(bad_env)
