import random
import string
from datetime import datetime
from Banking_agent.app.Schemas.profile_update import ProfileUpdateRequest


ALLOWED_FIELDS = {
    "email": "Email",
    "phone": "Contact_Number",
    "phone number": "Contact_Number",
    "contact": "Contact_Number",
    "contact number": "Contact_Number",
    "mobile": "Contact_Number",
    "mobile number": "Contact_Number",
    "address": "Address",
    "city": "City",
    "name": "Full_Name",
    "full name": "Full_Name",
}


def raise_profile_update_request(customer_name: str, field_to_update: str, new_value: str, reason: str = ""):
    """
    Raises a service request for profile update. Does NOT update the DB directly.
    Returns a request ID for tracking.
    """
    field_lower = field_to_update.strip().lower()
    mapped_field = ALLOWED_FIELDS.get(field_lower)

    if not mapped_field:
        return {
            "status": "error",
            "message": f"Profile updates for '{field_to_update}' are not supported over phone. Supported fields are: email, phone number, address, city, and name. For other changes, please visit your nearest branch."
        }

    if not new_value or not new_value.strip():
        return {
            "status": "error",
            "message": "The new value cannot be empty. Could you please provide the updated information?"
        }

    request_id = "PUR" + "".join(random.choices(string.digits, k=6))

    ProfileUpdateRequest(
        Request_ID=request_id,
        Customer_Name=customer_name,
        Field_Name=mapped_field,
        New_Value=new_value.strip(),
        Reason=reason.strip() if reason else "Customer requested update via phone",
        Status="PENDING",
        Timestamp=datetime.utcnow()
    ).save()

    return {
        "request_id": request_id,
        "status": "submitted",
        "field": mapped_field,
        "message": f"Your request to update {field_to_update} has been submitted successfully. Your request number is {request_id}. Our team will verify and process this within 1 to 2 business days. You will receive a confirmation on your registered email once the update is complete."
    }
