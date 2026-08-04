"""
Atlas web server - password hashing.

PBKDF2-HMAC-SHA256 via Python's stdlib hashlib, not a hand-rolled
scheme: unique random salt per hash, a work factor in line with
current OWASP guidance (600,000 iterations), constant-time comparison,
and a versioned encoded format so the algorithm can change later
without breaking already-issued hashes.

Encoded format: "pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>"

Nothing here ever sees or stores the plaintext password beyond the
single verify_password() call - only the encoded hash is meant to be
persisted (in ATLAS_PASSWORD_HASH).
"""

import base64
import hashlib
import hmac
import secrets

ALGORITHM_PREFIX = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
SALT_BYTES = 16


def hash_password(password, iterations=DEFAULT_ITERATIONS, salt=None):
    """Returns a versioned encoded hash string. `salt`/`iterations` are
    only ever overridden by tests (to keep test runs fast) - production
    callers should use the defaults."""
    if not password:
        raise ValueError("password must not be empty")

    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    hash_b64 = base64.urlsafe_b64encode(derived).decode("ascii").rstrip("=")
    return f"{ALGORITHM_PREFIX}${iterations}${salt_b64}${hash_b64}"


def verify_password(password, encoded_hash):
    """Constant-time verification. Returns False (never raises) for a
    malformed/unrecognized encoded hash, so a misconfigured
    ATLAS_PASSWORD_HASH fails closed rather than crashing the request."""
    if not password or not encoded_hash:
        return False

    try:
        algorithm, iterations_str, salt_b64, hash_b64 = encoded_hash.split("$", 3)
        if algorithm != ALGORITHM_PREFIX:
            return False
        iterations = int(iterations_str)
        salt = _b64_decode(salt_b64)
        expected = _b64_decode(hash_b64)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def _b64_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
