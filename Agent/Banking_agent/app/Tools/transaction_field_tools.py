from langchain.tools import tool
from pydantic import BaseModel, Field
from Banking_agent.app.Services.transaction_fields_services import fetch_transaction_field


class FetchTransactionFieldInput(BaseModel):
    """Input for fetching a transaction field."""
    customer_name: str = Field(description="Full name of the customer")
    field: str = Field(description="Field: Transaction_Amount, Transaction_Type, Transaction_Date, Account_Balance_After_Transaction")


@tool(args_schema=FetchTransactionFieldInput)
def fetch_transaction_field_tool(customer_name: str, field: str) -> dict:
    """
    Fetch latest transaction field.
    """
    try:
        if not customer_name or not field:
            return {"error": "Customer name or field not provided"}
        name = str(customer_name).replace("_", " ").title()
        return fetch_transaction_field(name, field)
    except Exception as e:
        return f"Error while running fetch_transaction_field_tool: {e}"