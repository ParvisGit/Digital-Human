import redis
import logging
from mongoengine.connection import get_db
from Banking_agent.app.db.mongo import connect_db

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
                            host="localhost",
                            port=6379,
                            decode_responses=True
                        )
def preload_prompts():
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
            redis_client.set(redis_key,prompt)
            count += 1
        logger.info("Loaded %d prompts into Redis",count)
    except Exception as e:
        logger.exception("Failed to preload prompts: %s", e)