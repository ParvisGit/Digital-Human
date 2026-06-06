import os
import logging
from pymongo import MongoClient

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("prompt_migrator")

# MongoDB Connection

MONGO_URI = ("mongodb://giniiris-voice:DnRGRJzCqSSw72akH58N_FBvNFCHeHOEWz7JzgKQNQinuWo0@9fea8197-616e-4aa8-ad5f-56452a96f42d.asia-south2.firestore.goog:443/giniiris-voice-cdr-db?loadBalanced=true&tls=true&authMechanism=SCRAM-SHA-256&retryWrites=false")

client = MongoClient(MONGO_URI)
db = client["giniiris-voice-cdr-db"]
collection = db["agent_prompts"]

# Prompt Directory
PROMPTS_DIR = "/home/giniiris_voice/AI_Backend/Digital-Human/Agent/Banking_agent/prompts"
if not os.path.exists(PROMPTS_DIR):
    raise FileNotFoundError(
        f"Prompt directory not found: {PROMPTS_DIR}"
    )

logger.info("Starting prompt migration from %s",PROMPTS_DIR)

migrated_count = 0

# Migration

for filename in os.listdir(PROMPTS_DIR):
    if not filename.endswith(".txt"):
        continue

    filepath = os.path.join(PROMPTS_DIR, filename)

    agent_name = filename.replace("_prompt.txt", "")

    try:
        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:
            prompt_text = f.read()

        result = collection.update_one(
            {"agent_name": agent_name},
            {
                "$set": {
                    "agent_name": agent_name,
                    "prompt": prompt_text,
                    "prompt_length": len(prompt_text)
                }
            },
            upsert=True
        )

        migrated_count += 1

        logger.info(
            "Migrated prompt for %s (%s chars)",
            agent_name,
            len(prompt_text)
        )

    except Exception as e:

        logger.exception(
            "Failed migrating prompt for %s",
            agent_name
        )

logger.info(
    "Migration completed. Total prompts migrated: %s",
    migrated_count
)