"""
Atlas web server - session management tests. Uses FakeSupabaseClient -
no network access, no applied migrations required.
"""

from server.sessions import create_session, revoke_session, validate_session
from server.supabase_client import FakeSupabaseClient

SECRET = "test-session-secret"


class TestCreateAndValidateSession:
    def test_freshly_created_session_is_valid(self):
        fake = FakeSupabaseClient()
        result = create_session(fake, SECRET, max_age_seconds=3600)
        assert validate_session(fake, SECRET, result.cookie_value) is True

    def test_session_stored_as_hash_not_raw_token(self):
        fake = FakeSupabaseClient()
        result = create_session(fake, SECRET, max_age_seconds=3600)
        token = result.cookie_value.split(".")[0]
        stored = fake.tables["auth_sessions"][0]
        assert stored["session_token_hash"] != token

    def test_tampered_cookie_rejected(self):
        fake = FakeSupabaseClient()
        result = create_session(fake, SECRET, max_age_seconds=3600)
        tampered = result.cookie_value[:-1] + ("x" if result.cookie_value[-1] != "x" else "y")
        assert validate_session(fake, SECRET, tampered) is False

    def test_wrong_secret_rejected(self):
        fake = FakeSupabaseClient()
        result = create_session(fake, SECRET, max_age_seconds=3600)
        assert validate_session(fake, "different-secret", result.cookie_value) is False

    def test_expired_session_rejected(self):
        fake = FakeSupabaseClient()
        result = create_session(fake, SECRET, max_age_seconds=-10)
        assert validate_session(fake, SECRET, result.cookie_value) is False

    def test_garbage_cookie_rejected(self):
        fake = FakeSupabaseClient()
        assert validate_session(fake, SECRET, "not-a-cookie") is False
        assert validate_session(fake, SECRET, "") is False
        assert validate_session(fake, SECRET, None) is False

    def test_unknown_session_rejected(self):
        fake = FakeSupabaseClient()
        # Well-formed signature, but never created - simulates a
        # forged token that happens to guess... nothing, since it
        # won't match a stored hash.
        from server.sessions import _sign
        fake_token = "made-up-token"
        cookie = f"{fake_token}.{_sign(fake_token, SECRET)}"
        assert validate_session(fake, SECRET, cookie) is False


class TestRevokeSession:
    def test_revoked_session_rejected(self):
        fake = FakeSupabaseClient()
        result = create_session(fake, SECRET, max_age_seconds=3600)
        revoke_session(fake, result.cookie_value)
        assert validate_session(fake, SECRET, result.cookie_value) is False

    def test_revoking_garbage_cookie_does_not_raise(self):
        fake = FakeSupabaseClient()
        revoke_session(fake, "not-a-cookie")  # should not raise
        revoke_session(fake, "")

    def test_revoking_one_session_does_not_affect_another(self):
        fake = FakeSupabaseClient()
        first = create_session(fake, SECRET, max_age_seconds=3600)
        second = create_session(fake, SECRET, max_age_seconds=3600)
        revoke_session(fake, first.cookie_value)
        assert validate_session(fake, SECRET, first.cookie_value) is False
        assert validate_session(fake, SECRET, second.cookie_value) is True



# Bounded expired/revoked-session cleanup now lives in server/cleanup.py
# (tests/test_server_cleanup.py) - the old purge_expired_sessions() did
# an unbounded full-table scan and was removed in favor of that.
