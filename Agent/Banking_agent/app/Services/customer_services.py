import logging
from Banking_agent.app.Schemas.fetch_balance import Customer

logger = logging.getLogger("banking_agent.db")

ALLOWED_CUSTOMER_FIELDS = {
    "Full_Name", "Age", "Gender", "City",
    "Email", "Contact_Number", "Cibil_score"
}


def fetch_customer_field(customer_name: str, field: str) -> dict:
    try:
        logger.info("[CUSTOMER_FIELD] Query: customer_name=%s field=%s", customer_name, field)
        if field not in ALLOWED_CUSTOMER_FIELDS:
            result = {"error": "Requested customer field is not permitted"}
            logger.info("[CUSTOMER_FIELD] Response: %s", result)
            return result
        customer = Customer.objects(Full_Name__iexact=customer_name).first()
        logger.info("[CUSTOMER_FIELD] Customer lookup: %s", customer.Full_Name if customer else "NOT FOUND")
        if not customer:
            result = {"error": "Customer not found"}
            logger.info("[CUSTOMER_FIELD] Response: %s", result)
            return result
        result = {"Customer_Name": customer.Full_Name, field: getattr(customer, field)}
        logger.info("[CUSTOMER_FIELD] Response: %s", result)
        return result
    except Exception as e:
        logger.exception("[CUSTOMER_FIELD] Error: %s", e)
        return f"Error with fetch_customer_field: {e}"
