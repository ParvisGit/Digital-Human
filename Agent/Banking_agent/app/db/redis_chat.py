"""
Redis checkpoint persistence (AVA-style).
Uses langgraph-checkpoint-redis when Redis is configured; falls back to InMemorySaver otherwise.
Requires Redis 8+ (or Redis Stack) with RedisJSON and RediSearch modules.
"""
import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from Banking_agent.app.config.redis_settings import (
    get_redis_conn_string,
    get_redis_ttl_config,
    is_redis_enabled,
)

logger = logging.getLogger("banking_agent.redis")

# Singleton checkpointer - created lazily
_checkpointer: Any = None
_use_redis: bool | None = None


def _create_redis_checkpointer():
    """Create RedisSaver from conn string. Called when Redis is enabled."""
    try:
        from langgraph.checkpoint.redis import RedisSaver

        conn_string = get_redis_conn_string()
        ttl_config = get_redis_ttl_config()

        if ttl_config:
            saver = RedisSaver.from_conn_string(conn_string, ttl=ttl_config)
        else:
            saver = RedisSaver.from_conn_string(conn_string)

        saver.setup()
        logger.info("Redis checkpointer initialized: %s", conn_string.split("@")[-1] if "@" in conn_string else conn_string)
        return saver
    except Exception as e:
        logger.warning("Failed to create Redis checkpointer: %s. Falling back to InMemorySaver.", e)
        return InMemorySaver()


def get_checkpointer():
    """
    Return the checkpointer for LangGraph.
    Uses Redis when REDIS_HOST is set and langgraph-checkpoint-redis is available;
    otherwise falls back to InMemorySaver.
    """
    global _checkpointer, _use_redis

    if _checkpointer is not None:
        return _checkpointer

    if is_redis_enabled():
        try:
            _checkpointer = _create_redis_checkpointer()
            _use_redis = not isinstance(_checkpointer, InMemorySaver)
        except ImportError as e:
            logger.warning(
                "langgraph-checkpoint-redis not installed. Install with: pip install langgraph-checkpoint-redis. %s",
                e,
            )
            _checkpointer = InMemorySaver()
            _use_redis = False
    else:
        _checkpointer = InMemorySaver()
        _use_redis = False
        logger.debug("Redis not configured (REDIS_HOST unset). Using InMemorySaver.")

    return _checkpointer


def is_using_redis() -> bool:
    """True if the active checkpointer is Redis-backed."""
    get_checkpointer()
    return _use_redis or False


# Legacy alias for compatibility with multiagent_flow_V2 etc.
redis_memory = None  # Lazy: use get_checkpointer() instead
