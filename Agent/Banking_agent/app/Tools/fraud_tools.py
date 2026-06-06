from langchain_core.tools import tool
from Banking_agent.app.Services.fraud_services import (
    create_fraud_case,
    block_card,
    freeze_account,
    flag_account,
    get_and_flag_suspicious_transactions,
    unblock_card,
    unfreeze_account,
    check_fraud_case_status
)


@tool
def report_fraud_tool(customer_name: str, message: str):
    """Report fraud and create a fraud case."""
    return create_fraud_case(customer_name, message)


@tool
def block_card_tool(customer_name: str):
    """Block customer's debit/credit card immediately."""
    return block_card(customer_name)


@tool
def freeze_account_tool(customer_name: str):
    """Freeze customer's account."""
    return freeze_account(customer_name)


@tool
def flag_account_tool(customer_name: str):
    """Flag account for suspicious activity monitoring."""
    return flag_account(customer_name)


@tool
def unblock_card_tool(customer_name: str):
    """Unblock a previously blocked debit or credit card."""
    return unblock_card(customer_name)


@tool
def unfreeze_account_tool(customer_name: str):
    """Unfreeze a previously frozen account."""
    return unfreeze_account(customer_name)


@tool
def check_fraud_case_status_tool(customer_name: str):
    """Check the status of fraud cases and actions taken on a customer's account."""
    return check_fraud_case_status(customer_name)


@tool
def suspicious_transactions_tool(customer_name: str):
    """Fetch and flag suspicious transactions."""
    return get_and_flag_suspicious_transactions(customer_name)