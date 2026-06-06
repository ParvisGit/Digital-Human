from mongoengine import Document, DynamicDocument, StringField, DecimalField, DateTimeField, ReferenceField,IntField
from Banking_agent.app.Schemas.fetch_balance import Account

class Transaction(Document):
    Customer_ID = IntField(required=True)
    TransactionID = IntField(required=True) 
    Transaction_Amount = DecimalField(required=True, precision=2)
    Transaction_Type = StringField(required=True) 
    Transaction_Date = DateTimeField(required=True)
    Account_Balance_After_Transaction = DecimalField(required=True, precision=2)
    Account_status = StringField(required=True)
    card_status = StringField(required=True)
    meta = {"collection": "Transactions_Collection"}