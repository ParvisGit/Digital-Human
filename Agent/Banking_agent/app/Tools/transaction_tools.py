from Banking_agent.app.Services.transaction_services import fetch_last_n_transactions
from langchain.tools import tool
from pydantic import BaseModel, Field


class FetchTransactionsInput(BaseModel):
    """Input for fetching last N transactions."""
    customer_name: str = Field(description="Full name of the customer")
    n: int = Field(default=5, description="Number of transactions to fetch")


@tool(args_schema=FetchTransactionsInput)
def fetch_last_n_transactions_tool(customer_name: str, n: int = 5) -> dict:
    """
    Fetch last N transactions for a customer.
    """
    try:
        if not customer_name:
            return {"error": "Customer name not provided"}
        name = str(customer_name).replace("_", " ").title()
        return fetch_last_n_transactions({"customer_name": name, "n": n})
    except Exception as e:
        return f"Error while running fetch_last_n_transactions_tool: {str(e)}"
