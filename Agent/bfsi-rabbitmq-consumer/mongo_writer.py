from datetime import datetime
from pymongo import MongoClient
import os
import logging

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb://giniiris-voice:DnRGRJzCqSSw72akH58N_FBvNFCHeHOEWz7JzgKQNQinuWo0@9fea8197-616e-4aa8-ad5f-56452a96f42d.asia-south2.firestore.goog:443/giniiris-voice-cdr-db?loadBalanced=true&tls=true&authMechanism=SCRAM-SHA-256&retryWrites=false"
    )

DB_NAME = os.getenv("MONGO_DB_NAME", "giniiris-voice-cdr-db")

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db["chat_logs"]

    # Verify connection
    client.admin.command("ping")
    logger.info("MongoDB connection established successfully")

except Exception as e:
    logger.exception("Failed to connect to MongoDB")
    raise


def save_chat(data):
    try:
        # Convert ISO timestamp string to native datetime
        if "timestamp" in data and isinstance(data["timestamp"], str):
            try:
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid timestamp format: %s",
                    data.get("timestamp")
                )

        result = collection.insert_one(data)

        logger.info(
            "Chat log saved successfully. Document ID: %s",
            result.inserted_id
        )

        return str(result.inserted_id)

    except Exception as e:
        logger.exception(
            "Failed to save chat data to MongoDB. Payload: %s",
            data
        )
        return None