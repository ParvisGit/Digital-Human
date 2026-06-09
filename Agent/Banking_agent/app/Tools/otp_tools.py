import logging
import re

from langchain_core.tools import tool
from Banking_agent.app.Services.otp_service import (
    generate_and_send_otp,
    generate_and_send_otp_email,
    verify_otp as _verify_otp,
)
from Banking_agent.app.Utils.phone_utils import normalize_phone_number

logger = logging.getLogger(__name__)


@tool
def send_otp_email_tool(customer_name: str, phone_number: str) -> dict:
    """Send a One-Time Password (OTP) to the customer's registered email address.
    Call this immediately after identity is verified with verify_customer_identity_tool.
    customer_name: verified customer full name.
    phone_number: registered phone number (used to look up email from DB).
    Handles mixed word/digit phone input."""
    # Normalize phone number
    normalized_phone = normalize_phone_number(str(phone_number))
    if normalized_phone != phone_number:
        logger.info("send_otp_email_tool: normalized '%s' -> '%s'", phone_number, normalized_phone)
    return generate_and_send_otp_email(customer_name, normalized_phone)


@tool
def send_otp_tool(customer_name: str, phone_number: str) -> dict:
    """Send a One-Time Password (OTP) via SMS to the customer's registered mobile number.
    Use this for high-security actions like blocking cards or freezing accounts.
    customer_name: verified customer full name.
    phone_number: registered phone number.
    Handles mixed word/digit phone input."""
    # Normalize phone number
    normalized_phone = normalize_phone_number(str(phone_number))
    if normalized_phone != phone_number:
        logger.info("send_otp_tool: normalized '%s' -> '%s'", phone_number, normalized_phone)
    return generate_and_send_otp(customer_name, normalized_phone)


def _normalize_otp_input(otp_input: str) -> str:
    """Normalize OTP input - remove spaces and extract digits."""
    # Remove all non-digit characters
    return re.sub(r'[^\d]', '', str(otp_input))


@tool
def verify_otp_tool(customer_name: str, otp_input: str) -> dict:
    """Verify the OTP spoken or typed by the customer.
    customer_name: the verified customer full name.
    otp_input: the digits the customer provided (e.g. '482931' or '4 8 2 9 3 1').
    Returns otp_verified=True on success, or otp_verified=False with attempts_left on failure."""
    # Normalize OTP input (remove spaces, extract digits)
    normalized_otp = _normalize_otp_input(otp_input)
    if normalized_otp != otp_input:
        logger.info("verify_otp_tool: normalized OTP '%s' -> '%s'", otp_input, normalized_otp)
    return _verify_otp(customer_name, normalized_otp)
