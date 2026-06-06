from Banking_agent.app.Services.balance_services import fetch_bank_balance_after_transaction
from langchain.tools import tool
from pydantic import BaseModel, Field


class FetchBalanceInput(BaseModel):
    """Input for fetching account balance."""
    customer_name: str = Field(description="Full name of the customer")


@tool(args_schema=FetchBalanceInput)
def fetch_account_balance_tool(customer_name: str) -> dict:
    """
    Fetch account balance after latest transaction.
    Input: customer_name - full name of the customer.
    """
    try:
        if not customer_name:
            return {"error": "Customer name not provided"}
        name = str(customer_name).replace("_", " ").title()
        return fetch_bank_balance_after_transaction(name)
    except Exception as e:
        return f"Got an error fetch_account_balance_tool: {e}"