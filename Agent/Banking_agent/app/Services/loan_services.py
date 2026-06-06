from Banking_agent.app.Schemas.loan import Loan
from Banking_agent.app.Schemas.fetch_balance import Customer


def get_loan_details(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    loan = Loan.objects(Customer_ID=customer.Customer_ID).first()
    if not loan:
        return {"error": "No loan record found for this customer"}

    return {
        "loan_id": loan.LoanID,
        "loan_type": loan.Loan_Type,
        "loan_amount": float(loan.Loan_Amount),
        "interest_rate": float(loan.Interest_Rate),
        "loan_term_months": loan.Loan_Term,
        "loan_status": loan.Loan_Status,
        "approval_date": loan.Approval_Rejection_Date,
    }


def get_loan_status(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    loan = Loan.objects(Customer_ID=customer.Customer_ID).first()
    if not loan:
        return {"error": "No loan record found"}

    return {
        "loan_type": loan.Loan_Type,
        "loan_status": loan.Loan_Status,
        "loan_amount": float(loan.Loan_Amount),
        "interest_rate": float(loan.Interest_Rate),
    }
