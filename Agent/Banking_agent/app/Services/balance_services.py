import logging
from Banking_agent.app.Schemas.fetch_balance import Customer, Account
from Banking_agent.app.Schemas.fetch_N_transaction import Transaction

logger = logging.getLogger("banking_agent.db")


def fetch_bank_balance_after_transaction(customer_name: str) -> dict:
    """
    Fetches bank balance after latest transaction.
    """
    try:
        logger.info("[BALANCE] Query: customer_name=%s", customer_name)
        customer = Customer.objects(Full_Name__iexact=customer_name).first()
        logger.info("[BALANCE] Customer lookup result: %s", customer.Full_Name if customer else "NOT FOUND")
        if not customer:
            result = {"error": "Customer not found"}
            logger.info("[BALANCE] Response: %s", result)
            return result
        account = Account.objects(Customer_ID=customer.Customer_ID).first()
        logger.info("[BALANCE] Account lookup result: %s", account.Account_Number if account else "NOT FOUND")
        if not account:
            result = {"error": "Account not found"}
            logger.info("[BALANCE] Response: %s", result)
            return result
        latest_txn = (Transaction.objects(Customer_ID=customer.Customer_ID)
                    .order_by("-Transaction_Date", "-TransactionID")
                    .first())
        logger.info("[BALANCE] Latest txn: date=%s id=%s balance_after=%s",
                    latest_txn.Transaction_Date if latest_txn else None,
                    latest_txn.TransactionID if latest_txn else None,
                    latest_txn.Account_Balance_After_Transaction if latest_txn else None)
        balance = (latest_txn.Account_Balance_After_Transaction
                if latest_txn and latest_txn.Account_Balance_After_Transaction is not None
                else account.Account_Balance)
        result = {"Customer_Name": customer.Full_Name, "Bank_Balance_After_Transaction": float(balance)}
        logger.info("[BALANCE] Response: %s", result)
        return result
    except Exception as e:
        logger.exception("[BALANCE] Error: %s", e)
        return f"Error with fetch_bank_balance_after_transaction: {e}"
