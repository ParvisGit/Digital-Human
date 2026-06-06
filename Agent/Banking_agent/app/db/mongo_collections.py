from pymongo import MongoClient

uri = "mongodb://giniiris-voice:DnRGRJzCqSSw72akH58N_FBvNFCHeHOEWz7JzgKQNQinuWo0@9fea8197-616e-4aa8-ad5f-56452a96f42d.asia-south2.firestore.goog:443/giniiris-voice-cdr-db?loadBalanced=true&tls=true&authMechanism=SCRAM-SHA-256&retryWrites=false"

client = MongoClient(uri)

print(client.list_database_names())

db = client["giniiris-voice-cdr-db"]

print(db.list_collection_names())