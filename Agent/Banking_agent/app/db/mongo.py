import logging
import mongoengine
import os

logger = logging.getLogger("banking_agent.mongo")


def connect_db():
    """
    Connects to MongoDB / Firestore MongoDB-compatible endpoint.
    Reads configuration from environment variables.
    """
    db_name = os.getenv("MONGO_DB_NAME", "giniiris-voice-cdr-db")
    mongo_uri = os.getenv(
        "MONGO_URI",
        "mongodb://giniiris-voice:DnRGRJzCqSSw72akH58N_FBvNFCHeHOEWz7JzgKQNQinuWo0@9fea8197-616e-4aa8-ad5f-56452a96f42d.asia-south2.firestore.goog:443/giniiris-voice-cdr-db?loadBalanced=true&tls=true&authMechanism=SCRAM-SHA-256&retryWrites=false"
    )
    logger.info("Connecting to MongoDB database: %s", db_name)
    try:
        mongoengine.connect(
            db=db_name,
            host=mongo_uri,
        )
        logger.info("MongoDB connected successfully.")
    except Exception as e:
        logger.error("Error connecting to MongoDB: %s", str(e))
        raise