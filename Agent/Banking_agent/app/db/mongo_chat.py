from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

#Chat history management with MongoDB
mongodb_uri = "mongodb://localhost:27017/"
mongodb_client = MongoClient(mongodb_uri)
CHECKPOINT_DB_NAME = 'langgraph_db'
CHECKPOINT_COLLECTION_NAME = 'checkpoints'

# Create the MongoDBSaver instance
mongodb_memory = MongoDBSaver(
                            client=mongodb_client,
                            db_name=CHECKPOINT_DB_NAME,
                            checkpoint_collection_name=CHECKPOINT_COLLECTION_NAME
                        )