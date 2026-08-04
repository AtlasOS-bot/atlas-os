"""
Atlas web server - CSRF and Origin validation tests. Pure functions,
no FastAPI/network involved.
"""

from server.config import Config
from server.csrf import (
    csrf_token_for, is_allowed_origin, is_valid_origin_string,
    session_token_from_cookie, validate_csrf_header, validate_origin,
)

SECRET = "test-csrf-secret"


def make_config(**overrides):
    defaults = dict(
        password_hash="x", session_secret="x", supabase_url="https://example.test",
        supabase_service_key="x", environment="production",
        public_origin="https://atlas.example.com",
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestCsrfToken:
    def test_valid_token_accepted(self):
        cookie = "abc123.sig"
        token = csrf_token_for("abc123", SECRET)
        assert validate_csrf_header(token, cookie, SECRET) is True

    def test_wrong_token_rejected(self):
        cookie = "abc123.sig"
        assert validate_csrf_header("wrong-token", cookie, SECRET) is False

    def test_missing_header_rejected(self):
        cookie = "abc123.sig"
        assert validate_csrf_header(None, cookie, SECRET) is False
        assert validate_csrf_header("", cookie, SECRET) is False

    def test_missing_cookie_rejected(self):
        token = csrf_token_for("abc123", SECRET)
        assert validate_csrf_header(token, None, SECRET) is False

    def test_token_bound_to_session_token_not_reusable_across_sessions(self):
        token_for_session_a = csrf_token_for("session-a", SECRET)
        cookie_for_session_b = "session-b.sig"
        assert validate_csrf_header(token_for_session_a, cookie_for_session_b, SECRET) is False

    def test_session_token_from_cookie(self):
        assert session_token_from_cookie("abc.def") == "abc"
        assert session_token_from_cookie("no-dot") is None
        assert session_token_from_cookie(None) is None
        assert session_token_from_cookie("") is None


class TestValidateOrigin:
    def test_matching_origin_accepted(self):
        assert validate_origin("https://atlas.example.com", None, "https://atlas.example.com") is True

    def test_cross_origin_rejected(self):
        assert validate_origin("https://evil.example.com", None, "https://atlas.example.com") is False

    def test_referer_fallback_when_origin_absent(self):
        assert validate_origin(None, "https://atlas.example.com/page", "https://atlas.example.com") is True

    def test_neither_header_rejected(self):
        assert validate_origin(None, None, "https://atlas.example.com") is False

    def test_origin_preferred_over_referer(self):
        assert validate_origin(
            "https://atlas.example.com", "https://evil.example.com", "https://atlas.example.com",
        ) is True


class TestIsValidOriginString:
    def test_valid_https_origin(self):
        assert is_valid_origin_string("https://atlas.example.com") is True

    def test_valid_https_origin_with_port(self):
        assert is_valid_origin_string("https://atlas.example.com:8443") is True

    def test_http_rejected_by_default(self):
        assert is_valid_origin_string("http://atlas.example.com") is False

    def test_trailing_slash_rejected(self):
        assert is_valid_origin_string("https://atlas.example.com/") is False

    def test_path_rejected(self):
        assert is_valid_origin_string("https://atlas.example.com/login") is False

    def test_query_string_rejected(self):
        assert is_valid_origin_string("https://atlas.example.com?x=1") is False

    def test_fragment_rejected(self):
        assert is_valid_origin_string("https://atlas.example.com#frag") is False

    def test_wildcard_rejected(self):
        assert is_valid_origin_string("https://*.example.com") is False
        assert is_valid_origin_string("*") is False

    def test_userinfo_rejected(self):
        assert is_valid_origin_string("https://user@atlas.example.com") is False
        assert is_valid_origin_string("https://evil.com@atlas.example.com") is False

    def test_whitespace_rejected(self):
        assert is_valid_origin_string("https://atlas.example.com ") is False
        assert is_valid_origin_string(" https://atlas.example.com") is False
        assert is_valid_origin_string("https://atlas .example.com") is False

    def test_empty_or_none_rejected(self):
        assert is_valid_origin_string("") is False
        assert is_valid_origin_string(None) is False

    def test_localhost_http_rejected_without_explicit_flag(self):
        assert is_valid_origin_string("http://localhost:3000", allow_http_localhost=False) is False

    def test_localhost_http_accepted_with_explicit_flag(self):
        assert is_valid_origin_string("http://localhost", allow_http_localhost=True) is True
        assert is_valid_origin_string("http://localhost:3000", allow_http_localhost=True) is True
        assert is_valid_origin_string("http://127.0.0.1", allow_http_localhost=True) is True
        assert is_valid_origin_string("http://127.0.0.1:8080", allow_http_localhost=True) is True

    def test_non_localhost_http_still_rejected_even_with_flag(self):
        assert is_valid_origin_string("http://example.com", allow_http_localhost=True) is False
        assert is_valid_origin_string("http://atlas.example.com", allow_http_localhost=True) is False

    def test_localhost_lookalike_hostname_rejected(self):
        # "localhost" only as the exact hostname, not as a substring.
        assert is_valid_origin_string("http://localhost.evil.com", allow_http_localhost=True) is False
        assert is_valid_origin_string("http://evil-localhost.com", allow_http_localhost=True) is False


class TestIsAllowedOriginProduction:
    def test_exact_match_accepted(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin("https://atlas.example.com", None, config) is True

    def test_completely_different_host_rejected(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin("https://evil.com", None, config) is False

    def test_lookalike_suffix_domain_rejected(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin("https://atlas.example.com.evil.com", None, config) is False

    def test_lookalike_prefix_domain_rejected(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin("https://evilatlas.example.com", None, config) is False

    def test_subdomain_rejected(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin("https://staging.atlas.example.com", None, config) is False

    def test_port_mismatch_rejected(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin("https://atlas.example.com:8443", None, config) is False

    def test_matching_port_accepted(self):
        config = make_config(public_origin="https://atlas.example.com:8443")
        assert is_allowed_origin("https://atlas.example.com:8443", None, config) is True

    def test_http_instead_of_https_rejected(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin("http://atlas.example.com", None, config) is False

    def test_referer_fallback_still_exact_match_only(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin(None, "https://atlas.example.com/page", config) is True
        assert is_allowed_origin(None, "https://evil.com/page", config) is False

    def test_no_headers_rejected(self):
        config = make_config(public_origin="https://atlas.example.com")
        assert is_allowed_origin(None, None, config) is False

    def test_production_with_no_public_origin_fails_closed(self):
        # Defensive path - load_config_from_env should never actually
        # produce this in production, but is_allowed_origin doesn't
        # rely on that: no public_origin + not development = always False.
        config = make_config(public_origin=None, environment="production")
        assert is_allowed_origin("https://atlas.example.com", None, config) is False
        assert is_allowed_origin("http://localhost:3000", None, config) is False


class TestIsAllowedOriginDevelopment:
    def test_localhost_accepted_when_no_public_origin_set(self):
        config = make_config(public_origin=None, environment="development")
        assert is_allowed_origin("http://localhost:3000", None, config) is True
        assert is_allowed_origin("http://127.0.0.1:8080", None, config) is True
        assert is_allowed_origin("http://localhost", None, config) is True

    def test_non_localhost_still_rejected_in_development(self):
        config = make_config(public_origin=None, environment="development")
        assert is_allowed_origin("https://evil.com", None, config) is False
        assert is_allowed_origin("http://evil.com", None, config) is False

    def test_localhost_lookalike_rejected_in_development(self):
        config = make_config(public_origin=None, environment="development")
        assert is_allowed_origin("http://localhost.evil.com", None, config) is False

    def test_explicit_public_origin_still_wins_over_localhost_in_development(self):
        # If ATLAS_PUBLIC_ORIGIN IS set, even in development mode, it's
        # the source of truth - localhost is not a bonus acceptance.
        config = make_config(public_origin="https://staging.atlas.example.com", environment="development")
        assert is_allowed_origin("http://localhost:3000", None, config) is False
        assert is_allowed_origin("https://staging.atlas.example.com", None, config) is True
