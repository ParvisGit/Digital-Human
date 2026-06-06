from langchain_core.tools import tool
from Banking_agent.app.Services.profile_update_services import raise_profile_update_request


@tool
def raise_profile_update_request_tool(customer_name: str, field_to_update: str, new_value: str, reason: str = ""):
    """Raise a service request to update customer profile information such as email, phone number, address, city, or name. This does not update directly — it creates a request that the bank team will verify and process."""
    return raise_profile_update_request(customer_name, field_to_update, new_value, reason)
