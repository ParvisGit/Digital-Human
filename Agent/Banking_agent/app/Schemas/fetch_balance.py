from mongoengine import Document,DynamicDocument, StringField, FloatField, IntField, DateField, ReferenceField, DateTimeField, DecimalField
import datetime

class Customer(Document):
    Customer_ID = IntField(required=True, unique=True)
    Full_Name = StringField(required=True)
    Age = IntField()
    Gender = StringField()
    Address = StringField()
    City = StringField()
    Contact_Number = StringField()
    Email = StringField()
    Cibil_score = IntField()
    meta = {'collection': 'Customers_Collection'}

class Account(Document):
    Customer_ID = IntField(required=True, unique=True)
    Account_Number = StringField(required=True, unique=True) 
    Account_Type = StringField(required=True) 
    Account_Balance = DecimalField(precision=2, default=0)
    Account_Status = StringField(default="ACTIVE") 
    Fraud_Flag = StringField(default="NO")  
    Date_Of_Account_Opening = DateTimeField()
    Branch_ID = StringField() 
    meta = {'collection': 'Accounts_Collection'}





