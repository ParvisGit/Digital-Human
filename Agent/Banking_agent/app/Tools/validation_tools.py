from Banking_agent.app.Services.validation_services import (
    fetch_customer_name,
    verify_customer_identity,
    verify_customer_last4_digit,
)
from Banking_agent.app.Utils.phone_utils import normalize_phone_number
from langchain.tools import tool
from pydantic import BaseModel, Field
import json
import logging

logger = logging.getLogger(__name__)


class FetchCustomerNameInput(BaseModel):
    """Input for looking up customer by phone number."""
    phone_number: str = Field(description="10-digit phone number of the customer (can include words like 'one', 'double 8', etc.)")


@tool(args_schema=FetchCustomerNameInput)
def fetch_customer_name_tool(phone_number: str) -> str:
    """Look up a customer by phone number. Returns customer name if found.
    Handles mixed word/digit input like '8 one 7 double 8 0 9 1 2 3'."""
    try:
        if isinstance(phone_number, str) and phone_number.startswith("{"):
            data = json.loads(phone_number)
            phone_number = data.get("phone_number", phone_number)
        
        # Normalize phone number (handles word inputs like "double 8", "one", etc.)
        normalized_phone = normalize_phone_number(str(phone_number))
        if normalized_phone != phone_number:
            logger.info("fetch_customer_name_tool: normalized '%s' -> '%s'", phone_number, normalized_phone)
        
        result = fetch_customer_name(normalized_phone)
        if isinstance(result, dict):
            return json.dumps(result)
        return str(result)
    except Exception as e:
        return f"Got an error in fetch_customer_name_tool: {e}"


class VerifyIdentityInput(BaseModel):
    """Input for verifying customer identity (name + phone)."""
    customer_name: str = Field(description="Full name of the customer (e.g., Joshua Hall)")
    phone_number: str = Field(description="10-digit phone number (can include words like 'one', 'double 8', etc.)")


@tool(args_schema=VerifyIdentityInput)
def verify_customer_identity_tool(customer_name: str, phone_number: str) -> str:
    """Verify customer identity by matching name and phone number. Returns identity_verified=True/False.
    Handles mixed word/digit phone input like '8 one 7 double 8 0 9 1 2 3'.
    On success, call send_otp_tool next to send an OTP before granting full access."""
    try:
        # Normalize phone number (handles word inputs like "double 8", "one", etc.)
        normalized_phone = normalize_phone_number(str(phone_number))
        if normalized_phone != phone_number:
            logger.info("verify_customer_identity_tool: normalized '%s' -> '%s'", phone_number, normalized_phone)
        
        result = verify_customer_identity(customer_name, normalized_phone)
        if isinstance(result, dict):
            matched = result.get("authenticated", False)
            return json.dumps({
                "identity_verified": matched,
                "customer_name": result.get("customer_name", customer_name),
                "phone_number": result.get("phone_number", normalized_phone),
            })
        return json.dumps({"identity_verified": False, "reason": "unexpected_response"})
    except Exception as e:
        return json.dumps({"identity_verified": False, "reason": str(e)})


@tool
def verify_customer_last4_digit_tool(phone_number: str, last_4_digits: str) -> bool:
    """Verify last 4 digits of phone number."""
    return verify_customer_last4_digit(phone_number, last_4_digits)

