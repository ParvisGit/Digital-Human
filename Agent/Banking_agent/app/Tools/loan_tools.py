from langchain_core.tools import tool
from Banking_agent.app.Services.loan_services import get_loan_details, get_loan_status


@tool
def fetch_loan_details_tool(customer_name: str):
    """Fetch full loan details for a customer: loan type, amount, interest rate, term, status, and approval date."""
    return get_loan_details(customer_name)


@tool
def fetch_loan_status_tool(customer_name: str):
    """Fetch the current loan status for a customer (Approved, Rejected, or Closed)."""
    return get_loan_status(customer_name)
