"""
Atlas web server - bounded cleanup tests: expired sessions, old revoked
sessions, old login attempts, and that every delete stays bounded.
"""

from datetime import datetime, timedelta, timezone

from server.cleanup import maybe_opportunistic_cleanup, run_full_cleanup
from server.config import Config
from server.supabase_client import FakeSupabaseClient


def make_config(**overrides):
    defaults = dict(
        password_hash="x", session_secret="x", supabase_url="https://example.test",
        supabase_service_key="x", public_origin="http://testserver",
        session_revoked_retention_days=30, login_attempt_retention_days=30,
        cleanup_batch_size=200, cleanup_probability=0.0,
    )
    defaults.update(overrides)
    return Config(**defaults)


def _iso(days_ago=0, hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)).isoformat()


class TestRunFullCleanup:
    def test_deletes_expired_sessions(self):
        fake = FakeSupabaseClient()
        fake.insert("auth_sessions", {"session_token_hash": "a", "expires_at": _iso(days_ago=1), "revoked_at": None})
        fake.insert("auth_sessions", {"session_token_hash": "b", "expires_at": _iso(days_ago=-1), "revoked_at": None})

        totals = run_full_cleanup(fake, make_config())
        assert totals["expired_sessions"] == 1
        remaining = {row["session_token_hash"] for row in fake.tables["auth_sessions"]}
        assert remaining == {"b"}

    def test_deletes_revoked_sessions_older_than_retention(self):
        fake = FakeSupabaseClient()
        fake.insert("auth_sessions", {
            "session_token_hash": "old-revoked", "expires_at": _iso(days_ago=-100),
            "revoked_at": _iso(days_ago=60),
        })
        fake.insert("auth_sessions", {
            "session_token_hash": "recent-revoked", "expires_at": _iso(days_ago=-100),
            "revoked_at": _iso(hours_ago=1),
        })

        totals = run_full_cleanup(fake, make_config(session_revoked_retention_days=30))
        assert totals["revoked_sessions"] == 1
        remaining = {row["session_token_hash"] for row in fake.tables["auth_sessions"]}
        assert remaining == {"recent-revoked"}

    def test_never_revoked_session_not_deleted_by_revoked_cleanup(self):
        fake = FakeSupabaseClient()
        fake.insert("auth_sessions", {
            "session_token_hash": "still-valid", "expires_at": _iso(days_ago=-100), "revoked_at": None,
        })
        run_full_cleanup(fake, make_config())
        assert len(fake.tables["auth_sessions"]) == 1

    def test_deletes_old_login_attempts(self):
        fake = FakeSupabaseClient()
        fake.insert("auth_login_attempts", {"attempted_at": _iso(days_ago=60), "success": False, "ip_address": None})
        fake.insert("auth_login_attempts", {"attempted_at": _iso(hours_ago=1), "success": False, "ip_address": None})

        totals = run_full_cleanup(fake, make_config(login_attempt_retention_days=30))
        assert totals["login_attempts"] == 1
        assert len(fake.tables["auth_login_attempts"]) == 1

    def test_clears_a_large_backlog_across_multiple_iterations(self):
        fake = FakeSupabaseClient()
        for i in range(450):
            fake.insert("auth_login_attempts", {
                "attempted_at": _iso(days_ago=60), "success": False, "ip_address": None,
            })
        totals = run_full_cleanup(fake, make_config(cleanup_batch_size=200, login_attempt_retention_days=30))
        assert totals["login_attempts"] == 450
        assert fake.tables["auth_login_attempts"] == []

    def test_stops_early_once_nothing_left(self):
        fake = FakeSupabaseClient()
        # Nothing to clean - should return immediately with all zeros,
        # not loop max_iterations times (can't directly observe the
        # loop count, but this at least proves it terminates correctly
        # and returns a well-formed zeroed result).
        totals = run_full_cleanup(fake, make_config())
        assert totals == {"expired_sessions": 0, "revoked_sessions": 0, "login_attempts": 0}

    def test_each_call_to_delete_bounded_batch_is_capped(self):
        """A single _run_cleanup_once pass never deletes more than
        cleanup_batch_size rows per category - verified indirectly via
        run_full_cleanup needing multiple iterations for a backlog
        larger than one batch (already covered above); this test
        checks the boundary precisely with batch_size=1."""
        fake = FakeSupabaseClient()
        for _ in range(3):
            fake.insert("auth_login_attempts", {
                "attempted_at": _iso(days_ago=60), "success": False, "ip_address": None,
            })
        from server.cleanup import _run_cleanup_once
        result = _run_cleanup_once(fake, make_config(cleanup_batch_size=1))
        assert result["login_attempts"] == 1  # exactly one batch's worth, not all 3


class TestMaybeOpportunisticCleanup:
    def test_does_not_run_when_probability_says_no(self):
        fake = FakeSupabaseClient()
        fake.insert("auth_login_attempts", {"attempted_at": _iso(days_ago=60), "success": False, "ip_address": None})
        result = maybe_opportunistic_cleanup(fake, make_config(), random_fn=lambda: 0.99)
        assert result is None
        assert len(fake.tables["auth_login_attempts"]) == 1  # untouched

    def test_runs_when_probability_says_yes(self):
        fake = FakeSupabaseClient()
        fake.insert("auth_login_attempts", {"attempted_at": _iso(days_ago=60), "success": False, "ip_address": None})
        result = maybe_opportunistic_cleanup(
            fake, make_config(cleanup_probability=0.02), random_fn=lambda: 0.0,
        )
        assert result is not None
        assert result["login_attempts"] == 1
        assert fake.tables["auth_login_attempts"] == []

    def test_supabase_failure_never_raises(self):
        class BrokenClient:
            def select_lt(self, *a, **k):
                from server.supabase_client import SupabaseError
                raise SupabaseError("simulated outage")

        result = maybe_opportunistic_cleanup(BrokenClient(), make_config(), random_fn=lambda: 0.0)
        assert result is None  # swallowed, not raised
