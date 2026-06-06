"""
OTP service: generates, sends (Twilio/mock), and verifies one-time passwords.
Keyed by customer_name. Uses MongoDB for persistence (survives process restarts).
Falls back to mock (log-only) if Twilio is unavailable.
"""
import os
import random
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger("banking_agent.otp")

OTP_EXPIRY_SECONDS = 300
MAX_OTP_ATTEMPTS   = 3

# MongoDB collection for OTP storage
_otp_collection = None


def _get_otp_collection():
    """Get the MongoDB OTP collection (lazy init)."""
    global _otp_collection
    if _otp_collection is None:
        from mongoengine.connection import get_db
        db = get_db()
        _otp_collection = db["otp_store"]
        # TTL index: auto-delete expired OTPs after 10 minutes
        _otp_collection.create_index("expiry_at", expireAfterSeconds=600)
    return _otp_collection


def _to_e164(phone: str) -> str:
    """Ensure phone is in E.164 format (+XXXXXXXXXXX).
    Handles Indian 10-digit numbers (6/7/8/9XXXXXXXXX) by prepending +91.
    Handles US 10-digit numbers by prepending +1.
    Leaves numbers already containing country code unchanged.
    """
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return phone

    if len(digits) >= 11:
        return f"+{digits}"

    if len(digits) == 10 and digits[0] in ("6", "7", "8", "9"):
        return f"+91{digits}"

    if len(digits) == 10:
        return f"+1{digits}"
    return f"+{digits}"


def _generate() -> str:
    return str(random.randint(100000, 999999))


def _send_via_twilio(to_number: str, otp: str) -> bool:
    """Send OTP SMS via Twilio. Returns True on success."""
    try:
        from twilio.rest import Client
        sid   = os.getenv("TWILIO_ACCOUNT_SID", "")
        token = os.getenv("TWILIO_AUTH_TOKEN", "")
        from_ = os.getenv("TWILIO_FROM_NUMBER", "")
        if not (sid and token and from_):
            logger.warning("[OTP] Twilio env vars missing — falling back to mock")
            return False
        client = Client(sid, token)
        client.messages.create(
            body=f"Your GiniBank OTP is {otp}. Valid for 5 minutes. Do not share this with anyone.",
            from_=from_,
            to=to_number,
        )
        logger.info("[OTP] SMS sent via Twilio to ...%s", to_number[-4:])
        return True
    except Exception as e:
        logger.warning("[OTP] Twilio send failed: %s", e)
        return False


def _send_via_email(customer_name: str, phone_number: str, otp: str) -> bool:
    """Send OTP via SMTP email. Looks up customer email from DB using phone number."""
    try:
        from Banking_agent.app.Services.validation_services import fetch_customer_email_by_phone
        from Banking_agent.app.config.smtp_settings import is_smtp_configured

        if not is_smtp_configured():
            logger.warning("[OTP] SMTP not configured — falling back to mock")
            return False

        result = fetch_customer_email_by_phone(phone_number)
        if not result.get("found") or not result.get("email"):
            logger.warning("[OTP] No email found for %s — falling back to mock", customer_name)
            return False

        email = result["email"]

        from Banking_agent.app.Services.validation_services import send_otp_email
        send_otp_email(email, otp)
        logger.info("[OTP] Email sent via SMTP to %s for %s", email, customer_name)
        return True
    except Exception as e:
        logger.warning("[OTP] SMTP send failed: %s", e)
        return False


def generate_and_send_otp_email(customer_name: str, phone_number: str) -> dict:
    """
    Generate a 6-digit OTP, store in MongoDB, send via SMTP email.
    Used for general authentication.
    Returns {"otp_sent": True, "method": "email" | "mock"}.
    """
    from datetime import datetime, timezone, timedelta

    otp = _generate()
    key = customer_name.strip().lower()
    expiry_at = datetime.now(timezone.utc) + timedelta(seconds=OTP_EXPIRY_SECONDS)

    coll = _get_otp_collection()
    coll.update_one(
        {"_id": key},
        {"$set": {
            "otp": otp,
            "expiry": time.time() + OTP_EXPIRY_SECONDS,
            "expiry_at": expiry_at,
            "attempts": 0,
            "phone_number": phone_number,
        }},
        upsert=True,
    )
    logger.info("[OTP] Stored in MongoDB for %s (expires in %ds)", customer_name, OTP_EXPIRY_SECONDS)

    sent_via_email = _send_via_email(customer_name, phone_number, otp)

    if sent_via_email:
        return {"otp_sent": True, "method": "email"}

    # Mock fallback
    logger.info("[OTP_MOCK] *** OTP for %s: %s (expires in 5 min) ***", customer_name, otp)
    return {"otp_sent": True, "method": "mock"}


def generate_and_send_otp(customer_name: str, phone_number: str) -> dict:
    """
    Generate a 6-digit OTP, store it in MongoDB, and send via Twilio (or mock).
    Returns {"otp_sent": True, "method": "sms" | "mock"}.
    """
    from datetime import datetime, timezone, timedelta

    otp = _generate()
    key = customer_name.strip().lower()
    expiry_at = datetime.now(timezone.utc) + timedelta(seconds=OTP_EXPIRY_SECONDS)

    coll = _get_otp_collection()
    coll.update_one(
        {"_id": key},
        {"$set": {
            "otp": otp,
            "expiry": time.time() + OTP_EXPIRY_SECONDS,
            "expiry_at": expiry_at,
            "attempts": 0,
            "phone_number": phone_number,
        }},
        upsert=True,
    )
    logger.info("[OTP] Stored in MongoDB for %s (expires in %ds)", customer_name, OTP_EXPIRY_SECONDS)

    to_number = _to_e164(phone_number)
    sent_via_twilio = _send_via_twilio(to_number, otp)

    if sent_via_twilio:
        return {"otp_sent": True, "method": "sms"}

    # Mock fallback — log OTP so dev/tester can read it
    logger.info("[OTP_MOCK] *** OTP for %s: %s (expires in 5 min) ***", customer_name, otp)
    return {"otp_sent": True, "method": "mock"}


def verify_otp(customer_name: str, otp_input: str) -> dict:
    """
    Verify the OTP spoken/typed by the customer.
    Reads from MongoDB — survives process restarts.
    Returns:
      {"otp_verified": True,  "customer_name": ...}            on success
      {"otp_verified": False, "reason": ..., "attempts_left": N} on failure
    """
    key = customer_name.strip().lower()
    coll = _get_otp_collection()
    record = coll.find_one({"_id": key})

    if not record:
        logger.warning("[OTP] No OTP found in MongoDB for %s", customer_name)
        return {"otp_verified": False, "reason": "no_otp_found", "attempts_left": 0}

    if time.time() > record["expiry"]:
        coll.delete_one({"_id": key})
        return {"otp_verified": False, "reason": "expired", "attempts_left": 0}

    # Increment attempts atomically
    coll.update_one({"_id": key}, {"$inc": {"attempts": 1}})
    attempts = record["attempts"] + 1

    # Normalize — strip spaces, handle spoken digits like "4 8 2 9 3 1"
    clean_input = "".join(c for c in otp_input if c.isdigit())

    if clean_input == record["otp"]:
        coll.delete_one({"_id": key})
        logger.info("[OTP] Verified successfully for %s", customer_name)
        return {"otp_verified": True, "customer_name": customer_name}

    attempts_left = MAX_OTP_ATTEMPTS - attempts
    if attempts_left <= 0:
        coll.delete_one({"_id": key})
        logger.warning("[OTP] Max attempts exceeded for %s", customer_name)
        return {"otp_verified": False, "reason": "max_attempts_exceeded", "attempts_left": 0}

    logger.warning("[OTP] Incorrect OTP for %s, attempts_left=%d", customer_name, attempts_left)
    return {"otp_verified": False, "reason": "incorrect", "attempts_left": attempts_left}
