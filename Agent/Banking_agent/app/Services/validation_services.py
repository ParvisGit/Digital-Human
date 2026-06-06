import logging
import smtplib
from email.mime.text import MIMEText
from Banking_agent.app.Schemas.fetch_balance import Customer
from Banking_agent.app.config.smtp_settings import (
    get_smtp_host, get_smtp_port, get_smtp_user,
    get_smtp_password, get_smtp_from_address, is_smtp_configured,
)

logger = logging.getLogger("banking_agent.db")


def fetch_customer_name(phone_number) -> dict:
    """Use this Service ONLY to check if a customer exists."""
    try:
        digits = "".join(c for c in str(phone_number) if c.isdigit())
        logger.info("[CUSTOMER_NAME] Query: phone_number=%s (digits=%s)", phone_number, digits)
        if not digits:
            result = {"found": False, "customer_name": None}
            logger.info("[CUSTOMER_NAME] Response: %s", result)
            return result

        customer = Customer.objects(Contact_Number=digits).first()
        if not customer:
            customer = Customer.objects(Contact_Number=int(digits)).first()
        if not customer:
            result = {"found": False, "customer_name": None}
            logger.info("[CUSTOMER_NAME] Response: %s", result)
            return result
        result = {"found": True, "customer_name": customer.Full_Name}
        logger.info("[CUSTOMER_NAME] Response: %s", result)
        return result
    except Exception as e:
        logger.exception("[CUSTOMER_NAME] Error: %s", e)
        return {"found": False, "error": str(e)}


def verify_customer_identity(customer_name: str, phone_number: str) -> dict:
    """Verify that a customer name and phone number match in the DB."""
    try:
        digits = "".join(c for c in str(phone_number) if c.isdigit())
        logger.info("[VERIFY_IDENTITY] Query: name=%s phone=%s", customer_name, digits)
        if not customer_name or not digits:
            result = {"authenticated": False, "reason": "Both customer name and phone number are required."}
            logger.info("[VERIFY_IDENTITY] Response: %s", result)
            return result
        customer = Customer.objects(Full_Name__iexact=customer_name.strip()).first()
        if not customer:
            result = {"authenticated": False, "reason": "Customer name not found."}
            logger.info("[VERIFY_IDENTITY] Response: %s", result)
            return result
        stored_phone = str(customer.Contact_Number)
        if stored_phone != digits:
            result = {"authenticated": False, "reason": "Phone number does not match our records for this customer."}
            logger.info("[VERIFY_IDENTITY] Response: stored=%s provided=%s", stored_phone, digits)
            return result
        result = {"authenticated": True, "customer_name": customer.Full_Name, "phone_number": stored_phone}
        logger.info("[VERIFY_IDENTITY] Response: %s", result)
        return result
    except Exception as e:
        logger.exception("[VERIFY_IDENTITY] Error: %s", e)
        return {"authenticated": False, "reason": str(e)}


def verify_customer_last4_digit(phone_number: str, last_4_digits: str) -> bool:
    """Verify last 4 digits of stored phone number."""
    try:
        logger.info("[VERIFY_LAST4] Query: phone=%s last4=%s", phone_number, last_4_digits)
        digits = "".join(c for c in str(phone_number) if c.isdigit())
        customer = Customer.objects(Contact_Number=digits).first()
        if not customer:
            customer = Customer.objects(Contact_Number=int(digits)).first()
        if not customer:
            logger.info("[VERIFY_LAST4] Response: Customer not found")
            return False
        stored_last4 = str(customer.Contact_Number)[-4:]
        match = stored_last4 == last_4_digits
        logger.info("[VERIFY_LAST4] Response: stored_last4=%s match=%s", stored_last4, match)
        return match
    except Exception as e:
        logger.exception("[VERIFY_LAST4] Error: %s", e)
        return False


def fetch_customer_email_by_phone(phone_number: str) -> dict:
    """Fetch customer email by phone number."""
    try:
        digits = "".join(c for c in str(phone_number) if c.isdigit())
        customer = Customer.objects(Contact_Number=digits).first()
        if not customer:
            customer = Customer.objects(Contact_Number=int(digits)).first()
        if not customer:
            return {"found": False}
        return {
            "found": True,
            "email": getattr(customer, "Email", None),
            "customer_name": customer.Full_Name,
        }
    except Exception as e:
        logger.exception("[FETCH_EMAIL_PHONE] Error: %s", e)
        return {"found": False}


def send_otp_email(receiver_email: str, otp: str):
    """Send OTP to the registered email via SMTP."""
    if not is_smtp_configured():
        raise Exception("SMTP not configured")
    host = get_smtp_host()
    port = get_smtp_port()
    user = get_smtp_user()
    password = get_smtp_password()
    sender = get_smtp_from_address()
    msg = MIMEText(
        f"Dear Customer,\n\n"
        f"Your One-Time Password (OTP) for authentication is: {otp}\n\n"
        f"This OTP is valid for the next 5 minutes. "
        f"Please do not share this OTP with anyone for security reasons.\n\n"
        f"If you did not request this, please ignore this email "
        f"or contact our support team immediately.\n\n"
        f"Thank you,\nGiniBank Support Team"
    )
    msg["Subject"] = "GiniBank OTP Authentication"
    msg["From"] = sender
    msg["To"] = receiver_email
    server = smtplib.SMTP(host, port)
    server.starttls()
    server.login(user, password)
    server.sendmail(sender, receiver_email, msg.as_string())
    server.quit()
    logger.info("[SMTP] OTP sent to %s", receiver_email)
