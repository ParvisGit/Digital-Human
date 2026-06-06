from langchain_core.tools import tool
from Banking_agent.app.Services.otp_service import (
    generate_and_send_otp,
    generate_and_send_otp_email,
    verify_otp as _verify_otp,
)


@tool
def send_otp_email_tool(customer_name: str, phone_number: str) -> dict:
    """Send a One-Time Password (OTP) to the customer's registered email address.
    Call this immediately after identity is verified with verify_customer_identity_tool.
    customer_name: verified customer full name.
    phone_number: registered phone number (used to look up email from DB)."""
    return generate_and_send_otp_email(customer_name, phone_number)


@tool
def send_otp_tool(customer_name: str, phone_number: str) -> dict:
    """Send a One-Time Password (OTP) via SMS to the customer's registered mobile number.
    Use this for high-security actions like blocking cards or freezing accounts.
    customer_name: verified customer full name.
    phone_number: registered phone number."""
    return generate_and_send_otp(customer_name, phone_number)


@tool
def verify_otp_tool(customer_name: str, otp_input: str) -> dict:
    """Verify the OTP spoken or typed by the customer.
    customer_name: the verified customer full name.
    otp_input: the digits the customer provided (e.g. '482931' or '4 8 2 9 3 1').
    Returns otp_verified=True on success, or otp_verified=False with attempts_left on failure."""
    return _verify_otp(customer_name, otp_input)
