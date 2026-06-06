from mongoengine import Document, IntField, DecimalField, StringField

class CreditCard(Document):
    Customer_ID = IntField(required=True)
    CardID = IntField(required=True, unique=True)
    Card_Type = StringField()              
    Credit_Limit = DecimalField(precision=2)
    Credit_Card_Balance = DecimalField(precision=2)
    Minimum_Payment_Due = DecimalField(precision=2)
    Payment_Due_Date = StringField()
    Last_Credit_Card_Payment_Date = StringField()

    meta = {'collection': 'CreditCards_Collection'}
