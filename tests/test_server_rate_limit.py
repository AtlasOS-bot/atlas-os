"""
Atlas web server - login rate limiting tests: per-IP lockout, the
global backstop, and their combination.
"""

from datetime import datetime, timedelta, timezone

from server.config import Config
from server.rate_limit import (
    is_globally_locked_out, is_locked_out, is_locked_out_for_ip, record_attempt,
)
from server.supabase_client import FakeSupabaseClient


def make_config(**overrides):
    defaults = dict(
        password_hash="x", session_secret="x", supabase_url="https://example.test",
        supabase_service_key="x", public_origin="http://testserver",
        lockout_threshold=5, global_lockout_threshold=20, lockout_window_seconds=900,
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestPerIpLockout:
    def test_not_locked_out_initially(self):
        fake = FakeSupabaseClient()
        assert is_locked_out_for_ip(fake, "203.0.113.5", threshold=5, window_seconds=900) is False

    def test_locked_out_at_threshold_for_that_ip(self):
        fake = FakeSupabaseClient()
        for _ in range(5):
            record_attempt(fake, success=False, ip_address="203.0.113.5")
        assert is_locked_out_for_ip(fake, "203.0.113.5", threshold=5, window_seconds=900) is True

    def test_other_ip_unaffected(self):
        fake = FakeSupabaseClient()
        for _ in range(5):
            record_attempt(fake, success=False, ip_address="203.0.113.5")
        assert is_locked_out_for_ip(fake, "203.0.113.99", threshold=5, window_seconds=900) is False

    def test_unknown_ip_never_locked_out_via_this_check(self):
        fake = FakeSupabaseClient()
        for _ in range(50):
            record_attempt(fake, success=False, ip_address=None)
        assert is_locked_out_for_ip(fake, None, threshold=5, window_seconds=900) is False

    def test_successful_attempts_do_not_count(self):
        fake = FakeSupabaseClient()
        for _ in range(10):
            record_attempt(fake, success=True, ip_address="203.0.113.5")
        assert is_locked_out_for_ip(fake, "203.0.113.5", threshold=5, window_seconds=900) is False

    def test_failures_outside_window_do_not_count(self):
        fake = FakeSupabaseClient()
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        for _ in range(5):
            fake.insert("auth_login_attempts", {
                "attempted_at": old, "success": False, "ip_address": "203.0.113.5",
            })
        assert is_locked_out_for_ip(fake, "203.0.113.5", threshold=5, window_seconds=900) is False


class TestGlobalLockout:
    def test_not_locked_out_below_threshold(self):
        fake = FakeSupabaseClient()
        for _ in range(19):
            record_attempt(fake, success=False, ip_address=f"203.0.113.{_ % 250}")
        assert is_globally_locked_out(fake, threshold=20, window_seconds=900) is False

    def test_locked_out_at_threshold_across_many_different_ips(self):
        """The whole point of the global check: many DIFFERENT IPs,
        none individually over the per-IP threshold, still trips it."""
        fake = FakeSupabaseClient()
        for i in range(20):
            record_attempt(fake, success=False, ip_address=f"203.0.113.{i}")
        assert is_globally_locked_out(fake, threshold=20, window_seconds=900) is True

    def test_successful_attempts_do_not_count(self):
        fake = FakeSupabaseClient()
        for i in range(30):
            record_attempt(fake, success=True, ip_address=f"203.0.113.{i}")
        assert is_globally_locked_out(fake, threshold=20, window_seconds=900) is False


class TestCombinedLockout:
    def test_locked_out_when_only_per_ip_threshold_hit(self):
        fake = FakeSupabaseClient()
        config = make_config(lockout_threshold=3, global_lockout_threshold=100)
        for _ in range(3):
            record_attempt(fake, success=False, ip_address="203.0.113.5")
        assert is_locked_out(fake, config, "203.0.113.5") is True
        # A different IP, with no failures of its own, is not caught
        # by the (very high) global threshold.
        assert is_locked_out(fake, config, "198.51.100.9") is False

    def test_locked_out_when_only_global_threshold_hit(self):
        fake = FakeSupabaseClient()
        config = make_config(lockout_threshold=100, global_lockout_threshold=10)
        for i in range(10):
            record_attempt(fake, success=False, ip_address=f"203.0.113.{i}")
        # None of these IPs individually hit the (very high) per-IP
        # threshold, but the global one is tripped for everyone.
        assert is_locked_out(fake, config, "198.51.100.9") is True

    def test_rotating_ips_cannot_bypass_the_global_ceiling(self):
        """Requirement: a conservative global limit stops an attacker
        from rotating across IPs specifically to dodge the per-IP
        limit. Each IP here only tries twice - well under a per-IP
        threshold of 5 - but 30 distinct IPs still trips the global
        ceiling of 20."""
        fake = FakeSupabaseClient()
        config = make_config(lockout_threshold=5, global_lockout_threshold=20)
        for i in range(30):
            record_attempt(fake, success=False, ip_address=f"203.0.113.{i}")
            record_attempt(fake, success=False, ip_address=f"203.0.113.{i}")
        assert is_locked_out(fake, config, "203.0.113.29") is True
        # Even a brand new IP that has never tried before is blocked by
        # the global ceiling.
        assert is_locked_out(fake, config, "198.51.100.200") is True

    def test_unknown_ip_relies_on_global_check_only(self):
        fake = FakeSupabaseClient()
        config = make_config(lockout_threshold=1, global_lockout_threshold=100)
        # Per-IP would trip instantly at threshold=1 if IP were known,
        # but it's None (untrusted/unavailable) - only the (untripped)
        # global check applies.
        record_attempt(fake, success=False, ip_address=None)
        assert is_locked_out(fake, config, None) is False
