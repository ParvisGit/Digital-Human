from mongoengine import Document, IntField, DecimalField, StringField

class Loan(Document):
    Customer_ID = IntField(required=True)
    LoanID = IntField(required=True, unique=True)
    Loan_Amount = DecimalField(precision=2)
    Loan_Type = StringField()          
    Interest_Rate = DecimalField(precision=2)
    Loan_Term = IntField()              
    Approval_Rejection_Date = StringField()
    Loan_Status = StringField()         

    meta = {'collection': 'Loans_Collection'}
