from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, DictField


class ChatLog(Document):

    session_id = StringField(required=True)
    user_message = StringField(required=True)
    bot_response = StringField()
    phone_number = StringField()
    agent = StringField()
    intent = StringField()
    metadata = DictField()
    timestamp = DateTimeField(default=datetime.utcnow)
    meta = {
        "collection": "chat_logs",
        "indexes": ["session_id", "timestamp"]
    }