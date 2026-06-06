from mongoengine import Document, StringField, DateTimeField
from datetime import datetime

class ChatHistory(Document):
    session_id = StringField(required=True)
    role = StringField(required=True, choices=["user", "assistant"])
    content = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    meta = {
        "collection": "Chat_History",
        "indexes": ["session_id"]
    }
