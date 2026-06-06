from langchain_core.tools import tool
from Banking_agent.app.Services.service_request_services import raise_service_request


@tool
def raise_service_request_tool(customer_name: str, request_type: str, reason: str = "", details: str = ""):
    """Raise a service request for actions that require manual processing by the bank team.
    Valid request_type values: credit_limit_increase, card_closure, transaction_reversal, credit_card_dispute.
    Use reason to capture why the customer is making the request.
    Use details for any additional information like disputed amount, transaction date, etc."""
    detail_dict = {}
    if details:
        detail_dict["additional_info"] = details
    return raise_service_request(customer_name, request_type, reason, detail_dict)
