from langchain_core.tools import tool
from Banking_agent.app.Services.grievance_services import register_complaint


@tool
def register_complaint_tool(customer_name: str, category: str, description: str):
    """Register a customer complaint or grievance. Category can be: fee_dispute, wrong_debit, service_issue, or general."""
    return register_complaint(customer_name, category, description)
