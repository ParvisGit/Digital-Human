import logging
from Banking_agent.app.Schemas.fetch_balance import Customer
from Banking_agent.app.Schemas.fetch_N_transaction import Transaction

logger = logging.getLogger("banking_agent.db")

ALLOWED_TRANSACTION_FIELDS = {
    "Transaction_Amount",
    "Transaction_Type",
    "Transaction_Date",
    "Account_Balance_After_Transaction"
}


def fetch_transaction_field(customer_name: str, field: str) -> dict:
    try:
        logger.info("[TXN_FIELD] Query: customer_name=%s field=%s", customer_name, field)
        if field not in ALLOWED_TRANSACTION_FIELDS:
            result = {"error": "Requested transaction field is not permitted"}
            logger.info("[TXN_FIELD] Response: %s", result)
            return result
        customer = Customer.objects(Full_Name__iexact=customer_name).first()
        logger.info("[TXN_FIELD] Customer lookup: %s", customer.Full_Name if customer else "NOT FOUND")
        if not customer:
            result = {"error": "Customer not found"}
            logger.info("[TXN_FIELD] Response: %s", result)
            return result
        txn = (Transaction.objects(Customer_ID=customer.Customer_ID)
                .order_by('-Transaction_Date', '-TransactionID')
                .first())
        if not txn:
            result = {"error": "No transactions found"}
            logger.info("[TXN_FIELD] Response: %s", result)
            return result
        result = {"Customer_Name": customer.Full_Name, field: getattr(txn, field)}
        logger.info("[TXN_FIELD] Response: %s", result)
        return result
    except Exception as e:
        logger.exception("[TXN_FIELD] Error: %s", e)
        return f"Error with fetch_transaction_field: {e}"
