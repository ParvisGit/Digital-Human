from mongoengine import Document, StringField, DateTimeField
from datetime import datetime

class ProfileUpdateRequest(Document):
    Request_ID = StringField(required=True, unique=True)
    Customer_Name = StringField(required=True)
    Field_Name = StringField(required=True)
    Current_Value = StringField()
    New_Value = StringField(required=True)
    Reason = StringField()
    Status = StringField(default="PENDING")
    Timestamp = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'Profile_Update_Requests',
        'indexes': ['Customer_Name', 'Status', 'Timestamp']
    }
