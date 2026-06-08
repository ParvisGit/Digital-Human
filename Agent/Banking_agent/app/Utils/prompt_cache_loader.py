import logging
import os
import redis

from mongoengine.connection import get_db
from Banking_agent.app.db.mongo import connect_db

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


def _should_load_from_db() -> bool:
    """Check if data should be loaded from database based on LOAD_FROM_DB env var."""
    value = os.environ.get("LOAD_FROM_DB", "false").lower().strip()
    return value in ("true", "1", "yes")


def preload_prompts():
    """
    Preload prompts from MongoDB into Redis cache.
    Only runs if LOAD_FROM_DB=true, otherwise skips (using file-based prompts).
    """
    if not _should_load_from_db():
        logger.info("Skipping prompts preload (LOAD_FROM_DB=false, using file-based prompts)")
        return
    
    try:
        connect_db()
        db = get_db()
        collection = db["agent_prompts"]
        documents = collection.find()
        count = 0
        for doc in documents:
            agent_name = doc.get("agent_name")
            prompt = doc.get("prompt")
            if not agent_name or not prompt:
                continue
            redis_key = f"prompt:{agent_name}"
            redis_client.set(redis_key, prompt)
            count += 1
        logger.info("Loaded %d prompts into Redis (LOAD_FROM_DB=true)", count)
    except Exception as e:
        logger.exception("Failed to preload prompts: %s", e)