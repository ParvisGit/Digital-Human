from langchain_core.tools import tool
from Banking_agent.app.Services.credit_card_services import (
    get_credit_card_details,
    get_credit_card_balance,
    get_credit_card_transactions,
    check_credit_card_eligibility,
    recommend_credit_card,
)


@tool
def fetch_credit_card_details_tool(customer_name: str):
    """Fetch full credit card details for a customer: card type, credit limit, current balance, available credit, minimum payment due, and payment due date."""
    return get_credit_card_details(customer_name)


@tool
def fetch_credit_card_balance_tool(customer_name: str):
    """Fetch the current credit card balance, minimum payment due, and payment due date for a customer."""
    return get_credit_card_balance(customer_name)


@tool
def fetch_credit_card_transactions_tool(customer_name: str, n: int = 5):
    """Fetch the last N credit card transactions for a customer. Defaults to 5 transactions."""
    return get_credit_card_transactions(customer_name, n)


@tool
def credit_card_eligibility_tool(customer_name: str):
    """Check if a customer is eligible for a credit card based on age and CIBIL score. Must be called BEFORE credit_card_recommendation_tool."""
    return check_credit_card_eligibility(customer_name)


@tool
def credit_card_recommendation_tool(customer_name: str):
    """Recommend the best credit card for a customer based on their CIBIL score. Only call this AFTER credit_card_eligibility_tool confirms eligibility."""
    return recommend_credit_card(customer_name)
