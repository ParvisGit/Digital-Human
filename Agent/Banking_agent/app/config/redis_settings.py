"""
Redis configuration (AVA-style).
Read from environment variables; used for session/checkpoint persistence.
"""
import os
from typing import Optional


def get_redis_host() -> Optional[str]:
    """Redis host. If None, Redis checkpointing is disabled."""
    return os.environ.get("REDIS_HOST") or os.environ.get("REDIS_HOSTNAME")


def get_redis_port() -> int:
    return int(os.environ.get("REDIS_PORT", "6379"))


def get_redis_password() -> Optional[str]:
    return os.environ.get("REDIS_PASSWORD") or None


def get_redis_db() -> int:
    return int(os.environ.get("REDIS_DB", "0"))


def is_redis_enabled() -> bool:
    """True if Redis is configured (host set) and should be used."""
    return bool(get_redis_host())


def get_redis_conn_string() -> str:
    """Build Redis connection string (redis://localhost:6379/0 or redis://:password@host:port/db)."""
    host = get_redis_host() or "localhost"
    port = get_redis_port()
    db = get_redis_db()
    password = get_redis_password()

    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def get_redis_ttl_config() -> Optional[dict]:
    """
    Optional TTL config for Redis checkpoints (session expiry).
    Returns None if not set (checkpoints persist indefinitely).
    """
    ttl_minutes = os.environ.get("REDIS_CHECKPOINT_TTL_MINUTES")
    if ttl_minutes is None:
        return None
    try:
        minutes = int(ttl_minutes)
        if minutes <= 0:
            return None
        return {
            "default_ttl": minutes,
            "refresh_on_read": os.environ.get("REDIS_TTL_REFRESH_ON_READ", "true").lower() == "true",
        }
    except ValueError:
        return None
