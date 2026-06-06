import json
import logging
import redis

from mongoengine.connection import get_db
from Banking_agent.app.db.mongo import connect_db

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

def get_interim_messages(tool_name: str):
    redis_key = f"interim:{tool_name}"

    try:
        data = redis_client.get(redis_key)
        if data:
            logger.info( "Interim messages fetched from Redis: %s",   tool_name)
            return json.loads(data)
    except Exception:
        logger.exception("Redis lookup failed for %s", tool_name )

    try:
        connect_db()
        db = get_db()
        doc = db["interim_messages"].find_one({"tool_name": tool_name})
        if not doc:
            return []
        messages = doc.get("messages", [])
        try:
            redis_client.set(
                redis_key,
                json.dumps(messages)
            )
        except Exception:
            pass

        logger.info("Interim messages fetched from MongoDB: %s",tool_name)
        return messages
    except Exception:
        logger.exception("Mongo fallback failed for %s", tool_name)
        return []