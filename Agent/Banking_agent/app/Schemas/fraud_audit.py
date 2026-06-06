from mongoengine import Document, StringField, DateTimeField, DictField
from datetime import datetime


class FraudAudit(Document):
    Customer_Name = StringField(required=True)
    Action = StringField(required=True)
    Metadata = DictField()
    Timestamp = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "Fraud_Audit_Logs",
        "indexes": ["Customer_Name", "Timestamp"]
    }