from Banking_agent.app.Services.validation_services import (
    fetch_customer_name,
    verify_customer_identity,
    verify_customer_last4_digit,
)
from langchain.tools import tool
from pydantic import BaseModel, Field
import json


class FetchCustomerNameInput(BaseModel):
    """Input for looking up customer by phone number."""
    phone_number: str = Field(description="10-digit phone number of the customer")


@tool(args_schema=FetchCustomerNameInput)
def fetch_customer_name_tool(phone_number: str) -> str:
    """Look up a customer by phone number. Returns customer name if found."""
    try:
        if isinstance(phone_number, str) and phone_number.startswith("{"):
            data = json.loads(phone_number)
            phone_number = data.get("phone_number", phone_number)
        result = fetch_customer_name(str(phone_number))
        if isinstance(result, dict):
            return json.dumps(result)
        return str(result)
    except Exception as e:
        return f"Got an error in fetch_customer_name_tool: {e}"


class VerifyIdentityInput(BaseModel):
    """Input for verifying customer identity (name + phone)."""
    customer_name: str = Field(description="Full name of the customer (e.g., Joshua Hall)")
    phone_number: str = Field(description="10-11 digit phone number of the customer")


@tool(args_schema=VerifyIdentityInput)
def verify_customer_identity_tool(customer_name: str, phone_number: str) -> str:
    """Verify customer identity by matching name and phone number. Returns identity_verified=True/False.
    On success, call send_otp_tool next to send an OTP before granting full access."""
    try:
        result = verify_customer_identity(customer_name, phone_number)
        if isinstance(result, dict):
            matched = result.get("authenticated", False)
            return json.dumps({
                "identity_verified": matched,
                "customer_name": result.get("customer_name", customer_name),
                "phone_number":   result.get("phone_number", phone_number),
            })
        return json.dumps({"identity_verified": False, "reason": "unexpected_response"})
    except Exception as e:
        return json.dumps({"identity_verified": False, "reason": str(e)})


@tool
def verify_customer_last4_digit_tool(phone_number: str, last_4_digits: str) -> bool:
    """Verify last 4 digits of phone number."""
    return verify_customer_last4_digit(phone_number, last_4_digits)

