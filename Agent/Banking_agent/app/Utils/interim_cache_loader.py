import json
import logging
import redis

from mongoengine.connection import get_db
from Banking_agent.app.db.mongo import connect_db

logger = logging.getLogger(__name__)

# Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

def preload_interim_messages():
    try:
        # Ensure MongoDB connection exists
        connect_db()
        # Get actual DB object
        db = get_db()
        collection = db["interim_messages"]
        documents = collection.find()
        count = 0
        for doc in documents:
            tool_name = doc.get("tool_name")
            messages = doc.get("messages", [])
            if not tool_name:
                continue
            redis_key = f"interim:{tool_name}"
            redis_client.set(
                redis_key,
                json.dumps(messages)
            )
            count += 1
        logger.info(
            "Loaded %d interim messages into Redis",
            count
        )
    except Exception as e:
        logger.exception("Failed to preload interim messages: %s",e)