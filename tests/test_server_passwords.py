"""
Atlas web server - password hashing tests.
"""

from server.passwords import hash_password, verify_password


class TestHashPassword:
    def test_same_password_different_salt_produces_different_hash(self):
        a = hash_password("correct horse battery staple", iterations=1000)
        b = hash_password("correct horse battery staple", iterations=1000)
        assert a != b

    def test_encoded_format_is_versioned(self):
        encoded = hash_password("x", iterations=1000)
        algorithm, iterations, salt, digest = encoded.split("$")
        assert algorithm == "pbkdf2_sha256"
        assert iterations == "1000"
        assert salt and digest

    def test_rejects_empty_password(self):
        try:
            hash_password("", iterations=1000)
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestVerifyPassword:
    def test_correct_password_verifies(self):
        encoded = hash_password("test-password-123", iterations=1000)
        assert verify_password("test-password-123", encoded) is True

    def test_wrong_password_fails(self):
        encoded = hash_password("test-password-123", iterations=1000)
        assert verify_password("wrong-password", encoded) is False

    def test_case_sensitive(self):
        encoded = hash_password("Password123", iterations=1000)
        assert verify_password("password123", encoded) is False

    def test_malformed_hash_fails_closed(self):
        assert verify_password("anything", "not-a-real-hash") is False
        assert verify_password("anything", "pbkdf2_sha256$notanumber$abc$def") is False
        assert verify_password("anything", "") is False

    def test_unknown_algorithm_prefix_fails(self):
        assert verify_password("x", "md5$1000$abc$def") is False

    def test_empty_password_never_verifies(self):
        encoded = hash_password("real-password", iterations=1000)
        assert verify_password("", encoded) is False

    def test_none_inputs_do_not_raise(self):
        assert verify_password(None, "pbkdf2_sha256$1000$abc$def") is False
        assert verify_password("x", None) is False
