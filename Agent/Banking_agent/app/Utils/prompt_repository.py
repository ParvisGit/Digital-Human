import redis
import logging
from mongoengine.connection import get_db

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

def get_prompt(agent_name: str) -> str | None:
    """
    Fetch prompt from Redis.
    Fallback to MongoDB if Redis fails or prompt missing.
    """
    redis_key = f"prompt:{agent_name}"
    try:
        logger.info("Checking Redis for prompt: %s", agent_name)
        prompt = redis_client.get(redis_key)
        if prompt:
            logger.info("Prompt fetched from Redis: %s", agent_name)
            return prompt
        logger.warning("Prompt not found in Redis for %s. Falling back to MongoDB.",agent_name)
    except Exception as e:
        logger.exception("Redis error while fetching prompt %s. Falling back to MongoDB.",agent_name,e)

    try:
        logger.info("Fetching prompt from MongoDB: %s", agent_name)
        db = get_db()
        doc = db["agent_prompts"].find_one({"agent_name": agent_name})
        if not doc:
            logger.error("Prompt not found in MongoDB: %s", agent_name)
            return None
        prompt = doc.get("prompt")
        logger.info("Prompt fetched from MongoDB: %s", agent_name)
        # Re-populate Redis
        try:
            redis_client.set(redis_key, prompt)
        except Exception:
            pass
        return prompt

    except Exception as e:
        logger.exception("MongoDB fallback failed for prompt %s",agent_name)
        return None