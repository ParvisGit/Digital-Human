import logging
from Banking_agent.app.Schemas.fetch_balance import Customer, Account

logger = logging.getLogger("banking_agent.db")

ALLOWED_ACCOUNT_FIELDS = {
    "Account_Number",
    "Account_Type",
    "Account_Balance",
    "Branch_ID",
    "Date_Of_Account_Opening"
}


def fetch_account_field(customer_name: str, field: str) -> dict:
    """
    Fetches the required Field of Accounts for a given customer name.
    """
    try:
        logger.info("[ACCOUNT_FIELD] Query: customer_name=%s field=%s", customer_name, field)
        if field not in ALLOWED_ACCOUNT_FIELDS:
            result = {"error": "Requested account field is not permitted"}
            logger.info("[ACCOUNT_FIELD] Response: %s", result)
            return result
        customer = Customer.objects(Full_Name__iexact=customer_name).first()
        logger.info("[ACCOUNT_FIELD] Customer lookup: %s", customer.Full_Name if customer else "NOT FOUND")
        if not customer:
            result = {"error": "Customer not found"}
            logger.info("[ACCOUNT_FIELD] Response: %s", result)
            return result
        account = Account.objects(Customer_ID=customer.Customer_ID).first()
        if not account:
            result = {"error": "Account not found"}
            logger.info("[ACCOUNT_FIELD] Response: %s", result)
            return result
        result = {"Customer_Name": customer.Full_Name, field: getattr(account, field)}
        logger.info("[ACCOUNT_FIELD] Response: %s", result)
        return result
    except Exception as e:
        logger.exception("[ACCOUNT_FIELD] Error: %s", e)
        return f"Error with fetch_account_field: {e}"
