import random
import string
from datetime import datetime
from Banking_agent.app.Schemas.complaint import Complaint


def register_complaint(customer_name: str, category: str, description: str):
    ticket_id = "GRV" + "".join(random.choices(string.digits, k=6))
    Complaint(
        Ticket_ID=ticket_id,
        Customer_Name=customer_name,
        Category=category,
        Description=description,
        Status="OPEN",
        Timestamp=datetime.utcnow()
    ).save()
    return {
        "ticket_id": ticket_id,
        "status": "registered",
        "message": f"Your complaint has been registered with ticket number {ticket_id}. Our team will contact you within 2 to 3 business days."
    }
