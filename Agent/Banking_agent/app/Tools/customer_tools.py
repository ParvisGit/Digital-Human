from langchain.tools import tool
from pydantic import BaseModel, Field
from Banking_agent.app.Services.customer_services import fetch_customer_field


class FetchCustomerFieldInput(BaseModel):
    """Input for fetching a customer field."""
    customer_name: str = Field(description="Full name of the customer")
    field: str = Field(description="Field name: Full_Name, Age, Gender, City, Email, Contact_Number, Cibil_score")


@tool(args_schema=FetchCustomerFieldInput)
def fetch_customer_field_tool(customer_name: str, field: str) -> dict:
    """
    Fetch a single customer field (Full_Name, Age, Gender, City, Email, Contact_Number, Cibil_score).
    """
    try:
        if not customer_name or not field:
            return {"error": "Customer name or field not provided"}
        name = str(customer_name).replace("_", " ").title()
        return fetch_customer_field(name, field)
    except Exception as e:
        return f"Error while running fetch_customer_field_tool: {e}"