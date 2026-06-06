"""
SMTP and OTP pepper settings from environment.
Used by smtp_mailer and otp_email_tools.
"""
import os


def get_smtp_host() -> str:
    return (os.environ.get("SMTP_HOST") or "").strip()


def get_smtp_port() -> int:
    try:
        return int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        return 587


def get_smtp_user() -> str:
    return (os.environ.get("SMTP_USER") or "").strip()


def get_smtp_password() -> str:
    return os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or ""


def get_smtp_from_address() -> str:
    return (os.environ.get("SMTP_FROM") or get_smtp_user() or "").strip()


def get_otp_pepper() -> str:
    """Secret mixed into OTP hashes; set OTP_PEPPER in production."""
    return (os.environ.get("OTP_PEPPER") or "").strip()


def is_smtp_configured() -> bool:
    """
    True when SMTP can send mail: host, user, and password must all be set.
    Port defaults to 587; SMTP_FROM defaults to SMTP_USER if unset.
    """
    return bool(get_smtp_host() and get_smtp_user() and get_smtp_password())
