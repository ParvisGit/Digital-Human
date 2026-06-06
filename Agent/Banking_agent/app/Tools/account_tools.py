from langchain.tools import tool
from pydantic import BaseModel, Field
from Banking_agent.app.Services.account_services import fetch_account_field


class FetchAccountFieldInput(BaseModel):
    """Input for fetching an account field."""
    customer_name: str = Field(description="Full name of the customer")
    field: str = Field(description="Field: Account_Number, Account_Type, Account_Balance, Branch_ID, Date_Of_Account_Opening")


@tool(args_schema=FetchAccountFieldInput)
def fetch_account_field_tool(customer_name: str, field: str) -> dict:
    """
    Fetch a single account field.
    """
    try:
        if not customer_name or not field:
            return {"error": "Customer name or field not provided"}
        name = str(customer_name).replace("_", " ").title()
        return fetch_account_field(name, field)
    except Exception as e:
        return f"Error with fetch_account_field_tool: {e}"