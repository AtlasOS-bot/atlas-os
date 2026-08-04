"""
Atlas web server - trusted client IP resolution tests.

FakeRequest is a minimal stand-in exposing only what resolve_client_ip
actually reads (.headers.get, .client.host) - no real Starlette
Request needed for these. End-to-end proof that spoofed headers can't
bypass lockout lives in tests/test_server_app.py, which drives this
through the real login route.
"""

from server.client_ip import resolve_client_ip
from server.config import Config


class FakeClient:
    def __init__(self, host):
        self.host = host


class FakeRequest:
    def __init__(self, headers=None, client_host="192.0.2.1"):
        self.headers = headers or {}
        self.client = FakeClient(client_host) if client_host else None


def make_config(**overrides):
    defaults = dict(
        password_hash="x", session_secret="x", supabase_url="https://example.test",
        supabase_service_key="x", environment="production",
        public_origin="https://atlas.example.com",
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestProductionTrustsVercelHeaders:
    def test_uses_x_forwarded_for_when_present(self):
        config = make_config(environment="production")
        request = FakeRequest(headers={"x-forwarded-for": "203.0.113.5"}, client_host="10.0.0.1")
        assert resolve_client_ip(request, config) == "203.0.113.5"

    def test_prefers_x_vercel_forwarded_for_over_x_forwarded_for(self):
        config = make_config(environment="production")
        request = FakeRequest(headers={
            "x-vercel-forwarded-for": "203.0.113.9",
            "x-forwarded-for": "203.0.113.5",
        })
        assert resolve_client_ip(request, config) == "203.0.113.9"

    def test_takes_only_first_entry_of_a_comma_separated_chain(self):
        config = make_config(environment="production")
        request = FakeRequest(headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1, 10.0.0.2"})
        assert resolve_client_ip(request, config) == "203.0.113.5"

    def test_none_when_no_trusted_header_present_in_production(self):
        """Falling back to request.client.host here would just be
        Vercel's own proxy IP - not the visitor's - so this must be
        None (unknown), not a silently-wrong value."""
        config = make_config(environment="production")
        request = FakeRequest(headers={}, client_host="10.0.0.1")
        assert resolve_client_ip(request, config) is None


class TestDevelopmentDoesNotTrustHeadersAtAll:
    def test_ignores_x_forwarded_for_entirely(self):
        config = make_config(environment="development", public_origin=None)
        request = FakeRequest(headers={"x-forwarded-for": "203.0.113.5"}, client_host="127.0.0.1")
        assert resolve_client_ip(request, config) == "127.0.0.1"

    def test_ignores_x_vercel_forwarded_for_entirely(self):
        config = make_config(environment="development", public_origin=None)
        request = FakeRequest(headers={"x-vercel-forwarded-for": "203.0.113.9"}, client_host="127.0.0.1")
        assert resolve_client_ip(request, config) == "127.0.0.1"

    def test_uses_raw_connection_address(self):
        config = make_config(environment="development", public_origin=None)
        request = FakeRequest(headers={}, client_host="198.51.100.1")
        assert resolve_client_ip(request, config) == "198.51.100.1"

    def test_none_when_no_connection_info_at_all(self):
        config = make_config(environment="development", public_origin=None)
        request = FakeRequest(headers={}, client_host=None)
        assert resolve_client_ip(request, config) is None


class TestSpoofingCannotSelectAnotherIdentity:
    def test_attacker_supplied_header_never_wins_off_vercel(self):
        """The core anti-spoofing property: outside of
        config.trust_vercel_ip_headers, an attacker can put anything
        in X-Forwarded-For and it is never used - the real ASGI-level
        connection address always wins."""
        config = make_config(environment="development", public_origin=None)
        victim_ip = "198.51.100.42"
        for spoofed in ["1.2.3.4", "127.0.0.1", "203.0.113.5, 203.0.113.6", "not-even-an-ip"]:
            request = FakeRequest(headers={"x-forwarded-for": spoofed}, client_host=victim_ip)
            assert resolve_client_ip(request, config) == victim_ip
