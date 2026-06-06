from mongoengine import Document, StringField, DateTimeField, DictField
from datetime import datetime


class ServiceRequest(Document):
    Request_ID = StringField(required=True, unique=True)
    Customer_Name = StringField(required=True)
    Request_Type = StringField(required=True)
    Details = DictField()
    Status = StringField(default="PENDING")
    Timestamp = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'Service_Requests',
        'indexes': ['Customer_Name', 'Request_Type', 'Status', 'Timestamp']
    }
