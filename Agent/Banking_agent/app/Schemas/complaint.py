from mongoengine import Document, StringField, DateTimeField
from datetime import datetime

class Complaint(Document):
    Ticket_ID = StringField(required=True, unique=True)
    Customer_Name = StringField(required=True)
    Category = StringField()
    Description = StringField()
    Status = StringField(default="OPEN")
    Timestamp = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'Complaints_Collection',
        'indexes': ['Customer_Name', 'Timestamp']
    }
