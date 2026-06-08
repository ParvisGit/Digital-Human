import json
import logging
import os
import redis

from mongoengine.connection import get_db
from Banking_agent.app.db.mongo import connect_db

logger = logging.getLogger(__name__)

INTERIM_COLLECTION = "banking_interim_messages"
REDIS_KEY_PREFIX = "banking_interim"

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


def _should_load_from_db() -> bool:
    """Check if data should be loaded from database based on LOAD_FROM_DB env var."""
    value = os.environ.get("LOAD_FROM_DB", "false").lower().strip()
    return value in ("true", "1", "yes")


def preload_interim_messages():
    """
    Preload interim messages from MongoDB into Redis cache.
    Only runs if LOAD_FROM_DB=true, otherwise skips (using file-based config).
    """
    if not _should_load_from_db():
        logger.info("Skipping interim messages preload (LOAD_FROM_DB=false, using file-based config)")
        return
    
    try:
        connect_db()
        db = get_db()
        collection = db[INTERIM_COLLECTION]
        documents = collection.find()
        count = 0
        for doc in documents:
            tool_name = doc.get("tool_name")
            messages = doc.get("messages", [])
            if not tool_name:
                continue
            redis_key = f"{REDIS_KEY_PREFIX}:{tool_name}"
            redis_client.set(
                redis_key,
                json.dumps(messages)
            )
            count += 1
        logger.info(
            "Loaded %d banking interim messages into Redis (LOAD_FROM_DB=true)",
            count
        )
    except Exception as e:
        logger.exception("Failed to preload banking interim messages: %s", e)