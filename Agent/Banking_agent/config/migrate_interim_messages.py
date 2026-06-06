import json
from pymongo import MongoClient

# Firestore MongoDB-compatible connection

MONGO_URI = ("mongodb://giniiris-voice:DnRGRJzCqSSw72akH58N_FBvNFCHeHOEWz7JzgKQNQinuWo0@9fea8197-616e-4aa8-ad5f-56452a96f42d.asia-south2.firestore.goog:443/giniiris-voice-cdr-db?loadBalanced=true&tls=true&authMechanism=SCRAM-SHA-256&retryWrites=false")

client = MongoClient(MONGO_URI)
db = client["giniiris-voice-cdr-db"]
collection = db["interim_messages"]

# Read Config File
with open("/home/giniiris_voice/AI_Backend/Digital-Human/Agent/Banking_agent/config/interim_message_config.json","r",encoding="utf-8") as f:
    data = json.load(f)

tool_mapping = data.get("tool_message_mapping",{})

migrated_count = 0

# Insert / Update
for tool_name, messages in tool_mapping.items():

    if isinstance(messages, str):
        messages = [messages]

    collection.update_one(
        {"tool_name": tool_name},
        {
            "$set": {
                "tool_name": tool_name,
                "messages": messages
            }
        },
        upsert=True
    )

    migrated_count += 1

    print(f"Migrated: {tool_name}")

print(
    f"\nSuccessfully migrated {migrated_count} tools "
    f"to interim_messages collection."
)