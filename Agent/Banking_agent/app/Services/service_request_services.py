import random
import string
from datetime import datetime
from Banking_agent.app.Schemas.service_request import ServiceRequest


VALID_REQUEST_TYPES = {
    "credit_limit_increase": {
        "label": "Credit Limit Increase",
        "prefix": "CLI",
        "turnaround": "3 to 5 business days",
    },
    "card_closure": {
        "label": "Credit Card Closure",
        "prefix": "CCL",
        "turnaround": "5 to 7 business days",
    },
    "transaction_reversal": {
        "label": "Transaction Reversal",
        "prefix": "TXR",
        "turnaround": "5 to 7 business days",
    },
    "credit_card_dispute": {
        "label": "Credit Card Charge Dispute",
        "prefix": "CCD",
        "turnaround": "7 to 10 business days",
    },
}


def raise_service_request(customer_name: str, request_type: str, reason: str = "", details: dict = None):
    """
    Raises a service request for actions that cannot be performed directly via the bot.
    Returns a request ID for tracking.
    """
    req_type_lower = request_type.strip().lower()
    config = VALID_REQUEST_TYPES.get(req_type_lower)

    if not config:
        valid_types = ", ".join(VALID_REQUEST_TYPES.keys())
        return {
            "status": "error",
            "message": f"Invalid request type '{request_type}'. Valid types are: {valid_types}"
        }

    prefix = config["prefix"]
    request_id = prefix + "".join(random.choices(string.digits, k=6))
    turnaround = config["turnaround"]
    label = config["label"]

    request_details = details or {}
    if reason:
        request_details["reason"] = reason

    ServiceRequest(
        Request_ID=request_id,
        Customer_Name=customer_name,
        Request_Type=req_type_lower,
        Details=request_details,
        Status="PENDING",
        Timestamp=datetime.utcnow()
    ).save()

    return {
        "request_id": request_id,
        "request_type": label,
        "status": "submitted",
        "message": f"Your {label} request has been submitted successfully. Your request number is {request_id}. Our team will review and process this within {turnaround}. You will receive a confirmation on your registered email."
    }
