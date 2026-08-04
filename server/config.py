"""
Atlas web server - configuration.

Config is loaded explicitly (load_config_from_env), never read from
os.environ scattered through the codebase - every other module takes a
Config instance as a parameter. This is what makes the whole server
testable without real environment variables or network access: tests
construct a Config directly with fake values.

ATLAS_ENV defaults to "production" - the safe default. Only an
explicit ATLAS_ENV=development relaxes the origin check to allow
localhost. In production, ATLAS_PUBLIC_ORIGIN is required and must be
a strictly well-formed https origin (see csrf.is_valid_origin_string) -
load_config_from_env refuses to start otherwise, rather than silently
falling back to something derived from a request header.
"""

import os
from dataclasses import dataclass

from server.csrf import is_valid_origin_string

DEFAULT_SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days
DEFAULT_LOCKOUT_THRESHOLD = 5
DEFAULT_GLOBAL_LOCKOUT_THRESHOLD = 20
DEFAULT_LOCKOUT_WINDOW_SECONDS = 15 * 60  # 15 minutes
DEFAULT_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB - well under Vercel's 4.5 MB hard limit
DEFAULT_SESSION_REVOKED_RETENTION_DAYS = 30
DEFAULT_LOGIN_ATTEMPT_RETENTION_DAYS = 30
DEFAULT_CLEANUP_PROBABILITY = 0.02
DEFAULT_CLEANUP_BATCH_SIZE = 200

VALID_ENVIRONMENTS = ("production", "development")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed -
    fails loudly at startup rather than silently running with no
    password check or a permissive origin fallback."""


@dataclass(frozen=True)
class Config:
    password_hash: str
    session_secret: str
    supabase_url: str
    supabase_service_key: str
    environment: str = "production"
    enable_demo: bool = False
    public_origin: str | None = None
    session_max_age_seconds: int = DEFAULT_SESSION_MAX_AGE_SECONDS
    lockout_threshold: int = DEFAULT_LOCKOUT_THRESHOLD
    global_lockout_threshold: int = DEFAULT_GLOBAL_LOCKOUT_THRESHOLD
    lockout_window_seconds: int = DEFAULT_LOCKOUT_WINDOW_SECONDS
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    session_revoked_retention_days: int = DEFAULT_SESSION_REVOKED_RETENTION_DAYS
    login_attempt_retention_days: int = DEFAULT_LOGIN_ATTEMPT_RETENTION_DAYS
    cleanup_probability: float = DEFAULT_CLEANUP_PROBABILITY
    cleanup_batch_size: int = DEFAULT_CLEANUP_BATCH_SIZE

    @property
    def trust_vercel_ip_headers(self):
        """Vercel overwrites x-forwarded-for (and x-vercel-forwarded-for)
        at its edge and never forwards a client-supplied value through
        (https://vercel.com/docs/headers/request-headers) - safe to
        trust ONLY when actually running in that environment. See
        server/client_ip.py."""
        return self.environment == "production"


def _require(env, name):
    value = env.get(name)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            "Atlas will not start without it - see the deployment plan "
            "for what each variable holds."
        )
    return value


def _bool_env(env, name, default=False):
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int_env(env, name, default):
    value = env.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _float_env(env, name, default):
    value = env.get(name)
    if value is None or not value.strip():
        return default
    return float(value)


def load_config_from_env(env=None):
    """Reads real process environment variables by default; tests pass
    an explicit dict instead so nothing here ever touches os.environ
    during a test run."""
    env = os.environ if env is None else env

    environment = (env.get("ATLAS_ENV") or "production").strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        raise ConfigError(
            f"ATLAS_ENV must be one of {VALID_ENVIRONMENTS!r}, got {environment!r}."
        )

    raw_public_origin = env.get("ATLAS_PUBLIC_ORIGIN")
    public_origin = raw_public_origin.rstrip("/") if raw_public_origin else None

    if environment == "production":
        if not public_origin:
            raise ConfigError(
                "ATLAS_PUBLIC_ORIGIN is required when ATLAS_ENV=production "
                "(the default) - it is the only source of truth for which "
                "Origin a state-changing request is allowed to come from. "
                "Set it to this deployment's exact https origin, e.g. "
                "https://atlas.example.com (no path, no trailing slash)."
            )
        if not is_valid_origin_string(public_origin, allow_http_localhost=False):
            raise ConfigError(
                f"ATLAS_PUBLIC_ORIGIN={raw_public_origin!r} is not a valid "
                "origin. It must be exactly scheme://host or "
                "scheme://host:port, https only, with no path, query, "
                "wildcard, or trailing slash."
            )
    elif public_origin and not is_valid_origin_string(public_origin, allow_http_localhost=True):
        raise ConfigError(
            f"ATLAS_PUBLIC_ORIGIN={raw_public_origin!r} is not a valid "
            "origin. It must be exactly scheme://host or "
            "scheme://host:port (http allowed only for localhost/127.0.0.1 "
            "in development mode)."
        )

    return Config(
        password_hash=_require(env, "ATLAS_PASSWORD_HASH"),
        session_secret=_require(env, "ATLAS_SESSION_SECRET"),
        supabase_url=_require(env, "SUPABASE_URL"),
        supabase_service_key=_require(env, "SUPABASE_SERVICE_KEY"),
        environment=environment,
        enable_demo=_bool_env(env, "ATLAS_ENABLE_DEMO", default=False),
        public_origin=public_origin,
        session_max_age_seconds=_int_env(
            env, "ATLAS_SESSION_MAX_AGE_SECONDS", DEFAULT_SESSION_MAX_AGE_SECONDS,
        ),
        lockout_threshold=_int_env(env, "ATLAS_LOCKOUT_THRESHOLD", DEFAULT_LOCKOUT_THRESHOLD),
        global_lockout_threshold=_int_env(
            env, "ATLAS_GLOBAL_LOCKOUT_THRESHOLD", DEFAULT_GLOBAL_LOCKOUT_THRESHOLD,
        ),
        lockout_window_seconds=_int_env(
            env, "ATLAS_LOCKOUT_WINDOW_SECONDS", DEFAULT_LOCKOUT_WINDOW_SECONDS,
        ),
        max_body_bytes=_int_env(env, "ATLAS_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES),
        session_revoked_retention_days=_int_env(
            env, "ATLAS_SESSION_RETENTION_DAYS", DEFAULT_SESSION_REVOKED_RETENTION_DAYS,
        ),
        login_attempt_retention_days=_int_env(
            env, "ATLAS_LOGIN_ATTEMPT_RETENTION_DAYS", DEFAULT_LOGIN_ATTEMPT_RETENTION_DAYS,
        ),
        cleanup_probability=_float_env(env, "ATLAS_CLEANUP_PROBABILITY", DEFAULT_CLEANUP_PROBABILITY),
        cleanup_batch_size=_int_env(env, "ATLAS_CLEANUP_BATCH_SIZE", DEFAULT_CLEANUP_BATCH_SIZE),
    )
